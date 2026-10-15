"""Read-only Microsoft sign-in with an operating-system protected token cache.

MSAL is imported only when calendar sign-in is requested. Tokens never enter
settings, workbook data, agenda snapshots or application diagnostics.
"""
from __future__ import annotations

import os
import logging
import hashlib
import sys
from pathlib import Path
import tempfile
import threading
from typing import Callable


CALENDAR_SCOPES = ("Calendars.Read", "Calendars.Read.Shared")
_MICROSOFT_DEVICE_SIGNIN_URLS = frozenset({
    "https://microsoft.com/devicelogin",
    "https://www.microsoft.com/devicelogin",
    "https://login.microsoft.com/device",
})
_CACHE_HEADER = b"CSPM-CALENDAR-DPAPI\x01"
_CACHE_ENTROPY = b"CSPM Microsoft 365 read-only calendar v1"


class CalendarAuthError(Exception):
    """Only safe, predetermined messages may cross the controller boundary."""

    def __init__(self, message: str, state: str = "error"):
        super().__init__(message)
        self.state = state


class CalendarCancelled(CalendarAuthError):
    def __init__(self):
        super().__init__("Calendar operation cancelled.", "disconnected")


def safe_microsoft_device_signin_url(value) -> bool:
    """Accept only Microsoft's known device-code entry pages, without parameters."""
    return isinstance(value, str) and value in _MICROSOFT_DEVICE_SIGNIN_URLS


def check_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise CalendarCancelled()


class WindowsUserProtector:
    """DPAPI current-user scope; deliberately no plaintext fallback."""

    @staticmethod
    def protect(payload: bytes) -> bytes:
        try:
            import win32crypt
            return win32crypt.CryptProtectData(
                payload, "CSPM Microsoft 365 calendar", _CACHE_ENTROPY,
                None, None, 1,  # CRYPTPROTECT_UI_FORBIDDEN; no LOCAL_MACHINE
            )
        except Exception:
            raise CalendarAuthError(
                "Windows could not protect the calendar sign-in cache. Sign-in was not saved."
            ) from None

    @staticmethod
    def unprotect(payload: bytes) -> bytes:
        try:
            import win32crypt
            return win32crypt.CryptUnprotectData(
                payload, _CACHE_ENTROPY, None, None, 1,
            )[1]
        except Exception:
            raise CalendarAuthError(
                "The saved calendar sign-in cannot be opened by this Windows user. Disconnect and sign in again."
            ) from None


class LinuxSecretServiceProtector:
    """Authenticated ciphertext with its key held by the desktop Secret Service.

    Bind to the persistent default collection explicitly: never fall back to
    a session collection, plaintext file, or an environment-selected backend.
    A locked/missing wallet fails safely; the user can unlock it and retry.
    """

    def __init__(self, profile_dir: Path, *, secret_module=None):
        self._module = secret_module
        self._profile = hashlib.sha256(str(Path(profile_dir).resolve()).encode()).hexdigest()

    def _key(self, *, create: bool) -> bytes:
        connection = None
        try:
            if self._module is None:
                import secretstorage
                self._module = secretstorage
            connection = self._module.dbus_init()
            collection = self._module.get_collection_by_alias(connection, "default")
            if collection.collection_path.rstrip("/").endswith("/session"):
                raise ValueError("A session wallet is not persistent")
            collection.ensure_not_locked()
            attributes = {"application": "CSPM", "purpose": "calendar-cache-encryption-v1",
                          "profile": self._profile}
            items = list(collection.search_items(attributes))
            if len(items) > 1:
                raise ValueError("Ambiguous wallet key")
            if items:
                return items[0].get_secret()
            if not create:
                raise ValueError("The wallet encryption key is missing")
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            collection.create_item("CSPM Microsoft 365 calendar encryption", attributes,
                                   key, replace=False, content_type="application/octet-stream")
            return key
        except Exception:
            raise CalendarAuthError(
                "The desktop wallet is unavailable or locked. Unlock the default Secret Service wallet and retry calendar sign-in."
            ) from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def protect(self, payload: bytes) -> bytes:
        try:
            from cryptography.fernet import Fernet
            return Fernet(self._key(create=True)).encrypt(payload)
        except CalendarAuthError:
            raise
        except Exception:
            raise CalendarAuthError("The desktop wallet could not protect the calendar sign-in cache.") from None

    def unprotect(self, payload: bytes) -> bytes:
        try:
            from cryptography.fernet import Fernet
            return Fernet(self._key(create=False)).decrypt(payload)
        except CalendarAuthError:
            raise
        except Exception:
            raise CalendarAuthError(
                "The saved calendar sign-in cannot be opened with this desktop wallet. Disconnect and sign in again."
            ) from None


class EncryptedTokenStore:
    """Atomic encrypted tokens and a nonsecret persistent disconnect marker."""

    def __init__(self, profile_dir: Path, protector=None):
        linux = protector is None and sys.platform.startswith("linux")
        self.path = Path(profile_dir) / "Microsoft365" / ("token_cache.secretservice" if linux else "token_cache.dpapi")
        self.marker_path = self.path.with_name("disconnected")
        self.protector = protector or (LinuxSecretServiceProtector(profile_dir) if linux else WindowsUserProtector())
        self._header = b"CSPM-CALENDAR-SECRET-SERVICE\x01" if linux else _CACHE_HEADER

    def load(self) -> str | None:
        if self.marker_path.exists():
            return None
        if not self.path.exists():
            return None
        try:
            blob = self.path.read_bytes()
            if not blob.startswith(self._header):
                raise ValueError("Unrecognized cache")
            return self.protector.unprotect(blob[len(self._header):]).decode("utf-8")
        except CalendarAuthError:
            raise
        except Exception:
            raise CalendarAuthError(
                "The saved calendar sign-in is unreadable. Disconnect and sign in again."
            ) from None

    def _write_blob(self, blob: bytes, cancel_event=None, target=None) -> None:
        target = target or self.path
        temp_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, filename = tempfile.mkstemp(prefix="token_cache_", suffix=".tmp", dir=self.path.parent)
            temp_path = Path(filename)
            with os.fdopen(handle, "wb") as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            check_cancelled(cancel_event)
            os.replace(temp_path, target)
        except CalendarCancelled:
            raise
        except Exception:
            raise CalendarAuthError("The protected calendar sign-in could not be saved.") from None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    # This is ciphertext, and replacing the cache already
                    # succeeded or failed with a safe error above.
                    pass

    def checkpoint(self) -> tuple[bytes | None, bytes | None]:
        """An internal rollback checkpoint containing encrypted/nonsecret bytes."""
        try:
            return (
                self.path.read_bytes() if self.path.exists() else None,
                self.marker_path.read_bytes() if self.marker_path.exists() else None,
            )
        except OSError:
            raise CalendarAuthError("The protected calendar sign-in state could not be read.") from None

    def restore_checkpoint(self, checkpoint) -> None:
        previous, marker = checkpoint
        # Keep loading disabled until the old encrypted state is fully restored.
        self._write_blob(b"disconnected\n", target=self.marker_path)
        try:
            if previous is None:
                self.path.unlink(missing_ok=True)
            else:
                self._write_blob(previous)
            if marker is None:
                self.marker_path.unlink(missing_ok=True)
            else:
                self._write_blob(marker, target=self.marker_path)
        except CalendarAuthError:
            raise
        except OSError:
            raise CalendarAuthError("The prior protected calendar sign-in could not be restored. Connect again.") from None

    def save(self, payload: str, cancel_event=None, *, connected=False) -> None:
        check_cancelled(cancel_event)
        blob = self._header + self.protector.protect(payload.encode("utf-8"))
        check_cancelled(cancel_event)
        previous = self.checkpoint()
        written = False
        try:
            self._write_blob(blob, cancel_event)
            written = True
            check_cancelled(cancel_event)
            if connected:
                # Silent token refresh cannot revoke an explicit disconnect.
                self.marker_path.unlink(missing_ok=True)
            check_cancelled(cancel_event)
        except CalendarCancelled:
            # Cancellation can arrive during the atomic replacement. Restore
            # the prior ciphertext without ever writing plaintext to disk.
            if written:
                self.restore_checkpoint(previous)
            raise
        except OSError:
            if written:
                self.restore_checkpoint(previous)
            raise CalendarAuthError("The protected calendar sign-in could not be saved.") from None

    def clear(self) -> None:
        # A failed ciphertext delete must never cause reconnection next launch.
        self._write_blob(b"disconnected\n", target=self.marker_path)
        try:
            self.path.unlink(missing_ok=True)
        except Exception:
            raise CalendarAuthError("The saved calendar sign-in could not be removed.") from None


def _safe_auth_failure(result) -> CalendarAuthError:
    code = result.get("error", "") if isinstance(result, dict) else ""
    if code in {"authorization_declined", "access_denied"}:
        return CalendarAuthError("Microsoft sign-in was declined.", "disconnected")
    if code in {"expired_token", "code_expired"}:
        return CalendarAuthError("The Microsoft sign-in code expired. Connect again.", "disconnected")
    if code in {"invalid_client", "unauthorized_client"}:
        return CalendarAuthError(
            "Microsoft rejected this app registration. Check its application ID, tenant and public-client setting."
        )
    if code in {"invalid_scope", "consent_required"}:
        return CalendarAuthError(
            "Read-only calendar consent is required. Your Microsoft 365 administrator may need to approve it."
        )
    return CalendarAuthError("Microsoft sign-in could not complete. Check connectivity and account permissions.")


class CalendarAuth:
    def __init__(self, profile_dir: Path, *, msal_module=None, store=None):
        self._module = msal_module
        self._store = store or EncryptedTokenStore(profile_dir)
        self._cache = None
        self._app = None
        self._app_key = None
        self._lock = threading.RLock()

    def _application(self, config):
        if self._module is None:
            try:
                import msal
                self._module = msal
            except ImportError:
                raise CalendarAuthError("Microsoft calendar support is missing from this installation.") from None
        # MSAL's malformed-response and refresh diagnostics can include raw
        # provider bodies even with enable_pii_log=False. Keep its package
        # diagnostics out of CSPM's runtime log; our public errors are safe.
        logging.getLogger("msal").setLevel(logging.CRITICAL + 1)
        for name in list(logging.Logger.manager.loggerDict):
            if name.startswith("msal."):
                logging.getLogger(name).setLevel(logging.CRITICAL + 1)
        key = (config["clientId"], config["tenantId"])
        if self._cache is None:
            self._cache = self._module.SerializableTokenCache()
            payload = self._store.load()
            if payload:
                try:
                    self._cache.deserialize(payload)
                except Exception:
                    self._cache = None
                    raise CalendarAuthError("The saved calendar sign-in is invalid. Disconnect and sign in again.") from None
        if self._app is None or self._app_key != key:
            try:
                self._app = self._module.PublicClientApplication(
                    config["clientId"],
                    authority="https://login.microsoftonline.com/" + config["tenantId"],
                    token_cache=self._cache, timeout=15,
                    enable_pii_log=False,
                )
                self._app_key = key
            except Exception:
                raise CalendarAuthError(
                    "Microsoft sign-in could not start. Check the app registration and your connection."
                ) from None
        return self._app

    @staticmethod
    def _matches(email: str, candidate: str) -> bool:
        return bool(email and candidate and email.casefold() == candidate.casefold())

    def _validate_token(self, result, expected_email: str, account=None) -> dict:
        if not isinstance(result, dict) or not result.get("access_token"):
            raise _safe_auth_failure(result)
        claims = result.get("id_token_claims") or {}
        claimed_email = claims.get("preferred_username") or claims.get("email") or claims.get("upn") or ""
        cached_email = (account or {}).get("username", "")
        # Silent responses sometimes omit ID-token claims. In that case the
        # explicitly selected MSAL account is the trusted account boundary.
        if claimed_email:
            matches = self._matches(expected_email, claimed_email)
        else:
            matches = self._matches(expected_email, cached_email)
        if not matches:
            raise CalendarAuthError(
                "The signed-in Microsoft account differs from the configured calendar account. Connect with that account.",
                "disconnected",
            )
        return {"access_token": result["access_token"], "accountEmail": expected_email}

    def get_token(self, config, cancel_event=None) -> dict:
        with self._lock:
            check_cancelled(cancel_event)
            if self._cache is None and self._store.load() is None:
                # Missing/explicitly disconnected sign-in is local state. Do
                # not contact Microsoft metadata until the user connects.
                raise CalendarAuthError("Connect your Microsoft 365 account to load meetings.", "disconnected")
            app = self._application(config)
            try:
                accounts = [a for a in app.get_accounts(username=config["accountEmail"])
                            if self._matches(config["accountEmail"], a.get("username", ""))]
            except Exception:
                raise CalendarAuthError("The saved Microsoft account could not be read. Connect again.", "disconnected") from None
            if len(accounts) != 1:
                raise CalendarAuthError("Connect your Microsoft 365 account to load meetings.", "disconnected")
            original_cache = self._cache.serialize()
            original_persisted = self._store.checkpoint()
            saved = False
            try:
                try:
                    result = app.acquire_token_silent(list(CALENDAR_SCOPES), account=accounts[0])
                except Exception:
                    raise CalendarAuthError("Microsoft calendar sign-in could not refresh. Check your connection.") from None
                check_cancelled(cancel_event)
                if not result:
                    raise CalendarAuthError("Microsoft calendar sign-in has expired. Connect again.", "disconnected")
                token = self._validate_token(result, config["accountEmail"], accounts[0])
                if self._cache.has_state_changed:
                    self._store.save(self._cache.serialize(), cancel_event=cancel_event)
                    saved = True
                check_cancelled(cancel_event)
                return token
            except CalendarAuthError:
                self._cache.deserialize(original_cache)
                if saved:
                    self._store.restore_checkpoint(original_persisted)
                raise

    def connect(self, config, challenge_callback: Callable[[dict], None], cancel_event) -> dict:
        with self._lock:
            check_cancelled(cancel_event)
            app = self._application(config)
            original_cache = self._cache.serialize()
            original_persisted = self._store.checkpoint()
            saved = False
            done = threading.Event()
            watcher = None
            try:
                # login_hint assists Microsoft account routing; account identity
                # is still enforced after authentication, since hints are not proof.
                flow = app.initiate_device_flow(
                    scopes=list(CALENDAR_SCOPES), params={"login_hint": config["accountEmail"]},
                )
                check_cancelled(cancel_event)
                if not isinstance(flow, dict) or not flow.get("user_code"):
                    raise _safe_auth_failure(flow)
                uri = flow.get("verification_uri", "")
                if not safe_microsoft_device_signin_url(uri):
                    raise CalendarAuthError("Microsoft returned an unsupported device sign-in link. Please update CSPM.")
                challenge_callback({
                    "user_code": flow["user_code"], "verification_uri": uri,
                    "expires_in": flow.get("expires_in", 900), "accountEmail": config["accountEmail"],
                })
                check_cancelled(cancel_event)

                def stop_polling():
                    while not done.wait(0.1):
                        if cancel_event is not None and cancel_event.is_set():
                            flow["expires_at"] = 0  # documented MSAL polling cancellation
                            return

                watcher = threading.Thread(target=stop_polling, name="calendar-signin-cancel", daemon=True)
                watcher.start()
                result = app.acquire_token_by_device_flow(flow)
                check_cancelled(cancel_event)
                token = self._validate_token(result, config["accountEmail"])
                self._store.save(self._cache.serialize(), cancel_event=cancel_event, connected=True)
                saved = True
                check_cancelled(cancel_event)
                return token
            except CalendarAuthError:
                self._cache.deserialize(original_cache)
                if saved:
                    self._store.restore_checkpoint(original_persisted)
                raise
            except Exception:
                self._cache.deserialize(original_cache)
                raise CalendarAuthError(
                    "Microsoft sign-in could not complete. Check connectivity, registration and account permissions."
                ) from None
            finally:
                done.set()
                if watcher is not None:
                    watcher.join(timeout=0.2)

    def disconnect(self) -> None:
        with self._lock:
            try:
                self._store.clear()
            finally:
                self._cache = None
                self._app = None
                self._app_key = None
