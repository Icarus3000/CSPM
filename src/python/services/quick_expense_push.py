"""Web Push Notification Service for CSPM Quick Expense.

Implements:
- RFC 8292: Voluntary Application Server Identification (VAPID) using ES256 ECDSA P-256 JWT
- RFC 8291: Message Encryption for Web Push using 'aes128gcm' Content-Encoding with ECDH, HKDF-SHA256, and AES-128-GCM
- Thread-safe storage for VAPID keypair, device subscriptions, and version tracking
- Automatic 404/410 endpoint pruning
"""
from __future__ import annotations

import base64
import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

VAPID_SUBJECT = "mailto:cory@coryschneiderlaw.ca"
_STORAGE_LOCK = threading.RLock()


def _b64url_encode(data: bytes) -> str:
    """Encode bytes to RFC 7515 / 8291 base64url string without trailing padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data_str: str) -> bytes:
    """Decode RFC 7515 / 8291 base64url string with optional missing padding."""
    s = (data_str or "").strip()
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _resolve_push_storage_path() -> Path:
    """Locate or create the thread-safe JSON state file in CSPM data directory."""
    candidates: List[Path] = []
    # 1. Check if AppPaths is importable
    try:
        from services.paths import AppPaths
        paths = AppPaths(root=AppPaths.project_root())
        data_d = paths.data_dir()
        if data_d:
            candidates.append(data_d)
        master_d = paths.master_data_dir()
        if master_d and master_d.exists():
            candidates.append(master_d)
    except Exception:
        pass

    # 2. Local fallback directories
    home = Path.home()
    candidates.extend([
        home / ".local" / "share" / "CSPM" / "data",
        home / "AppData" / "Local" / "CSPM" / "data",
        Path(__file__).resolve().parents[3] / "data",
        Path(__file__).resolve().parents[2] / "data",
    ])

    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            return cand / "quick_expense_push_state.json"
        except OSError:
            continue

    fallback = Path("/tmp") / "quick_expense_push_state.json"
    return fallback


class PushManager:
    """Manages VAPID keys, Web Push subscriptions, and notification delivery."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or _resolve_push_storage_path()
        self._state: Dict[str, Any] = {}
        self._vapid_private_key: Optional[Any] = None
        self._vapid_public_key_b64: str = ""
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        with _STORAGE_LOCK:
            self._load_state()
            if _CRYPTO_AVAILABLE:
                self._ensure_vapid_keys()

    def _load_state(self) -> None:
        if self.storage_path.exists():
            try:
                txt = self.storage_path.read_text(encoding="utf-8")
                self._state = json.loads(txt)
            except Exception:
                self._state = {}
        else:
            self._state = {}

        if "subscriptions" not in self._state or not isinstance(self._state["subscriptions"], list):
            self._state["subscriptions"] = []
        if "vapid" not in self._state or not isinstance(self._state["vapid"], dict):
            self._state["vapid"] = {}
        if "last_notified_version" not in self._state:
            self._state["last_notified_version"] = ""

    def _save_state(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.storage_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.storage_path)
        except Exception as exc:
            print(f"[PushManager] Failed to persist push state: {exc}", file=sys.stderr)

    def _ensure_vapid_keys(self) -> None:
        vapid_dict = self._state.get("vapid", {})
        pub_b64 = vapid_dict.get("public_key")
        priv_b64 = vapid_dict.get("private_key")

        if pub_b64 and priv_b64:
            try:
                priv_bytes = _b64url_decode(priv_b64)
                priv_num = int.from_bytes(priv_bytes, "big")
                self._vapid_private_key = ec.derive_private_key(priv_num, ec.SECP256R1())
                self._vapid_public_key_b64 = pub_b64
                return
            except Exception as exc:
                print(f"[PushManager] Re-generating invalid VAPID keys: {exc}", file=sys.stderr)

        # Generate new P-256 keypair
        priv_key = ec.generate_private_key(ec.SECP256R1())
        pub_key = priv_key.public_key()

        # 65-byte uncompressed point
        pub_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        priv_bytes = priv_key.private_numbers().private_value.to_bytes(32, "big")

        self._vapid_private_key = priv_key
        self._vapid_public_key_b64 = _b64url_encode(pub_bytes)
        priv_b64_str = _b64url_encode(priv_bytes)

        self._state["vapid"] = {
            "public_key": self._vapid_public_key_b64,
            "private_key": priv_b64_str,
            "subject": VAPID_SUBJECT,
        }
        self._save_state()

    def get_public_key(self) -> str:
        with _STORAGE_LOCK:
            return self._vapid_public_key_b64

    def subscribe(
        self,
        subscription_dict: Dict[str, Any],
        username: str = "",
        platform: str = "",
        user_agent: str = "",
    ) -> Dict[str, Any]:
        """Upsert a Web Push subscription."""
        endpoint = str(subscription_dict.get("endpoint") or "").strip()
        keys = subscription_dict.get("keys") or {}
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()

        if not endpoint or not p256dh or not auth:
            return {"ok": False, "message": "Invalid subscription: missing endpoint or keys."}

        norm_user = str(username or "cory").strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        with _STORAGE_LOCK:
            self._load_state()
            subs = self._state["subscriptions"]
            existing = next((s for s in subs if s.get("endpoint") == endpoint), None)
            if existing:
                existing["keys"] = {"p256dh": p256dh, "auth": auth}
                existing["username"] = norm_user
                if platform:
                    existing["platform"] = platform
                if user_agent:
                    existing["user_agent"] = user_agent
                existing["updated_at"] = now_iso
            else:
                subs.append({
                    "endpoint": endpoint,
                    "keys": {"p256dh": p256dh, "auth": auth},
                    "username": norm_user,
                    "platform": platform or "unknown",
                    "user_agent": user_agent or "unknown",
                    "updated_at": now_iso,
                })
            self._save_state()

        return {"ok": True, "count": len(self._state["subscriptions"])}

    def unsubscribe(self, endpoint: str) -> Dict[str, Any]:
        """Remove a Web Push subscription by endpoint."""
        target = str(endpoint or "").strip()
        if not target:
            return {"ok": False, "message": "Missing endpoint."}

        with _STORAGE_LOCK:
            self._load_state()
            before = len(self._state["subscriptions"])
            self._state["subscriptions"] = [
                s for s in self._state["subscriptions"] if s.get("endpoint") != target
            ]
            after = len(self._state["subscriptions"])
            self._save_state()

        return {"ok": True, "removed": before - after}

    def prune_endpoint(self, endpoint: str) -> None:
        """Silently remove a dead or expired (404/410) endpoint."""
        with _STORAGE_LOCK:
            self._load_state()
            self._state["subscriptions"] = [
                s for s in self._state["subscriptions"] if s.get("endpoint") != endpoint
            ]
            self._save_state()

    def list_subscriptions(
        self,
        target_username: Optional[str] = None,
        exclude_username: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with _STORAGE_LOCK:
            self._load_state()
            res = []
            for s in self._state.get("subscriptions", []):
                u = str(s.get("username") or "").lower()
                if target_username and u != target_username.lower():
                    continue
                if exclude_username and u == exclude_username.lower():
                    continue
                res.append(dict(s))
            return res

    def get_last_notified_version(self) -> str:
        with _STORAGE_LOCK:
            self._load_state()
            return str(self._state.get("last_notified_version") or "")

    def set_last_notified_version(self, ver: str) -> None:
        with _STORAGE_LOCK:
            self._load_state()
            self._state["last_notified_version"] = str(ver or "")
            self._save_state()

    def create_vapid_auth_header(self, endpoint: str) -> str:
        """Create RFC 8292 ES256 VAPID Authorization header."""
        if not _CRYPTO_AVAILABLE or not self._vapid_private_key:
            raise RuntimeError("cryptography is required for VAPID ES256 signing")

        parsed = urllib.parse.urlparse(endpoint)
        aud = f"{parsed.scheme}://{parsed.netloc}"

        header = {"typ": "JWT", "alg": "ES256"}
        now = int(time.time())
        claims = {
            "aud": aud,
            "exp": now + 43200,  # 12 hours
            "sub": VAPID_SUBJECT,
        }

        h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        c_b64 = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{c_b64}".encode("ascii")

        der_sig = self._vapid_private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der_sig)
        raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        sig_b64 = _b64url_encode(raw_sig)

        jwt = f"{h_b64}.{c_b64}.{sig_b64}"
        return f"vapid t={jwt}, k={self._vapid_public_key_b64}"

    @staticmethod
    def encrypt_payload(
        payload: bytes,
        ua_pub_b64: str,
        auth_b64: str,
    ) -> bytes:
        """Encrypt payload using RFC 8291 'aes128gcm' Content-Encoding."""
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography is required for RFC 8291 aes128gcm payload encryption")

        ua_pub_bytes = _b64url_decode(ua_pub_b64)
        auth_bytes = _b64url_decode(auth_b64)

        if len(ua_pub_bytes) != 65 or ua_pub_bytes[0] != 4:
            raise ValueError(f"Invalid user agent public key (must be 65-byte uncompressed point, got {len(ua_pub_bytes)})")
        if len(auth_bytes) < 16:
            raise ValueError(f"Invalid user agent auth secret (must be >= 16 bytes, got {len(auth_bytes)})")

        ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_bytes)

        # 1. Ephemeral sender keypair
        as_priv = ec.generate_private_key(ec.SECP256R1())
        as_pub_bytes = as_priv.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        # 2. ECDH shared secret
        ecdh_secret = as_priv.exchange(ec.ECDH(), ua_pub)

        # 3. HKDF derivation
        salt = os.urandom(16)
        auth_info = b"WebPush: info\x00" + ua_pub_bytes + as_pub_bytes

        prk = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=auth_bytes,
            info=auth_info,
        ).derive(ecdh_secret)

        cek = HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=salt,
            info=b"Content-Encoding: aes128gcm\x00",
        ).derive(prk)

        nonce = HKDF(
            algorithm=hashes.SHA256(),
            length=12,
            salt=salt,
            info=b"Content-Encoding: nonce\x00",
        ).derive(prk)

        # 4. RFC 8291 record padding with delimiter \x02
        rs = 4096
        padded = payload + b"\x02"

        # 5. AES-128-GCM encryption
        ciphertext = AESGCM(cek).encrypt(nonce, padded, b"")

        # 6. Header: salt(16) || rs(4, big-endian) || idlen(1) || as_pub(65)
        header = salt + struct.pack(">I", rs) + bytes([len(as_pub_bytes)]) + as_pub_bytes
        return header + ciphertext

    def send_notification(
        self,
        subscription: Dict[str, Any],
        payload: Any,
        ttl: int = 86400,
        urgency: str = "high",
    ) -> bool:
        """Send an RFC 8292 / RFC 8291 Web Push notification to an endpoint."""
        if not _CRYPTO_AVAILABLE:
            return False

        endpoint = str(subscription.get("endpoint") or "").strip()
        keys = subscription.get("keys") or {}
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()

        if not endpoint or not p256dh or not auth:
            return False

        if isinstance(payload, (dict, list)):
            raw_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, str):
            raw_payload = payload.encode("utf-8")
        else:
            raw_payload = bytes(payload)

        try:
            encrypted_body = self.encrypt_payload(raw_payload, p256dh, auth)
            auth_header = self.create_vapid_auth_header(endpoint)
        except Exception as exc:
            print(f"[PushManager] Encryption/VAPID failed for {endpoint[:30]}...: {exc}", file=sys.stderr)
            return False

        req = urllib.request.Request(
            endpoint,
            data=encrypted_body,
            headers={
                "Content-Encoding": "aes128gcm",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(encrypted_body)),
                "TTL": str(max(60, int(ttl))),
                "Urgency": urgency,
                "Authorization": auth_header,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                return resp.status in (200, 201, 202)
        except urllib.error.HTTPError as http_err:
            if http_err.code in (404, 410):
                # Subscription expired or unregistered by client; prune automatically
                self.prune_endpoint(endpoint)
            return False
        except Exception as exc:
            # Non-fatal network timeout / connection drop
            return False


# Singleton instance
_GLOBAL_MANAGER: Optional[PushManager] = None


def get_push_manager() -> PushManager:
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is None:
        with _STORAGE_LOCK:
            if _GLOBAL_MANAGER is None:
                _GLOBAL_MANAGER = PushManager()
    return _GLOBAL_MANAGER


def get_vapid_public_key() -> str:
    return get_push_manager().get_public_key()


def subscribe(
    subscription: Dict[str, Any],
    username: str = "",
    platform: str = "",
    user_agent: str = "",
) -> Dict[str, Any]:
    return get_push_manager().subscribe(subscription, username=username, platform=platform, user_agent=user_agent)


def unsubscribe(endpoint: str) -> Dict[str, Any]:
    return get_push_manager().unsubscribe(endpoint)


def broadcast_push(
    title: str,
    body: str,
    target_username: Optional[str] = None,
    exclude_username: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """Send push notification to matching subscriptions. Non-blocking when spawned in thread."""
    mgr = get_push_manager()
    subs = mgr.list_subscriptions(target_username=target_username, exclude_username=exclude_username)
    if not subs:
        return 0

    payload = {
        "title": title,
        "body": body,
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "tag": "qe-push-" + str(int(time.time())),
        "data": data or {},
    }

    sent = 0
    for s in subs:
        try:
            if mgr.send_notification(s, payload):
                sent += 1
        except Exception:
            pass
    return sent


def notify_expense_saved(saved_entry: Dict[str, Any], saved_by_user: str) -> int:
    """Notify Cory when Deborah logs an expense, or notify other devices."""
    saved_user = str(saved_by_user or "").strip().lower()
    payee = str(saved_entry.get("payee") or "Expense").strip()
    amt = float(saved_entry.get("amount") or 0.0)
    amt_str = f"${amt:.2f}"
    stream_name = str(saved_entry.get("streamShortLabel") or saved_entry.get("streamId") or "").strip()
    cat_name = str(saved_entry.get("categoryName") or "").strip()

    detail_label = f"{stream_name} · {cat_name}" if (stream_name and cat_name) else (cat_name or stream_name or "Personal")

    if saved_user == "deborah":
        title = "New Expense Logged by Deborah"
        body = f"{payee} · {amt_str} ({detail_label})"
        target = "cory"
        exclude = "deborah"
    else:
        title = f"New Expense Logged by {saved_user.title()}"
        body = f"{payee} · {amt_str} ({detail_label})"
        target = None
        exclude = saved_user

    data = {
        "type": "NEW_EXPENSE",
        "transactionId": saved_entry.get("transactionId") or "",
        "payee": payee,
        "amount": amt,
        "url": "/?source=pwa&action=check",
    }
    return broadcast_push(title=title, body=body, target_username=target, exclude_username=exclude, data=data)


def check_version_and_notify(new_version: str) -> int:
    """Check if the server version has changed, and if so notify all subscribed devices."""
    if not new_version:
        return 0
    mgr = get_push_manager()
    last_ver = mgr.get_last_notified_version()
    if not last_ver:
        # First startup: record version silently so we don't spam devices on reboot
        mgr.set_last_notified_version(new_version)
        return 0

    if last_ver != new_version:
        mgr.set_last_notified_version(new_version)
        title = "⚡ Quick Expense Updated"
        body = f"Version {new_version} is now live."
        data = {"type": "LPN_APP_UPDATE", "version": new_version, "url": "/?source=pwa"}
        return broadcast_push(title=title, body=body, data=data)

    return 0


def send_test_push(username: str = "cory") -> int:
    """Send a friendly test push notification to the user's subscribed devices."""
    title = "🔔 Quick Expense Notifications Active"
    body = f"Test notification delivered successfully at {time.strftime('%H:%M:%S')}."
    data = {"type": "TEST_PUSH", "time": time.time(), "url": "/?source=pwa"}
    return broadcast_push(title=title, body=body, target_username=username, data=data)
