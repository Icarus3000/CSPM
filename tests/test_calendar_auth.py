from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import textwrap
import threading
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "python"))
from services.calendar_auth import (
    CALENDAR_SCOPES, CalendarAuth, CalendarAuthError, CalendarCancelled,
    EncryptedTokenStore, WindowsUserProtector,
)


CONFIG = {"clientId": "d1234567-1234-1234-1234-123456789abc", "tenantId": "organizations", "accountEmail": "lawyer@example.test"}


class FakeProtector:
    def protect(self, payload):
        return bytes(value ^ 0xAC for value in payload)

    def unprotect(self, payload):
        return self.protect(payload)


class FakeStore:
    def __init__(self):
        self.payload = None
        self.saved = []
        self.cleared = False

    def load(self):
        return self.payload

    def save(self, value, cancel_event=None, *, connected=False):
        self.payload = value
        self.saved.append(value)

    def checkpoint(self):
        return self.payload

    def restore_checkpoint(self, value):
        self.payload = value

    def clear(self):
        self.payload = None
        self.cleared = True


class FakeCache:
    def __init__(self):
        self.payload = "cached account"
        self.has_state_changed = False

    def serialize(self):
        return self.payload

    def deserialize(self, value):
        self.payload = value


class FakeApp:
    def __init__(self, cache):
        self.cache = cache
        self.accounts = [{"username": CONFIG["accountEmail"], "home_account_id": "bound-account"}]
        self.result = {"access_token": "secret-access-token", "id_token_claims": {"preferred_username": CONFIG["accountEmail"]}}
        self.scopes = []
        self.initiate_kwargs = None
        self.flow = {"user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin", "expires_at": time.time() + 900, "expires_in": 900}
        self.block = False

    def get_accounts(self, username=None):
        return self.accounts

    def acquire_token_silent(self, scopes, account):
        self.scopes.append(scopes)
        return self.result

    def initiate_device_flow(self, **kwargs):
        self.initiate_kwargs = kwargs
        return self.flow

    def acquire_token_by_device_flow(self, flow):
        while self.block and flow["expires_at"] > 0:
            time.sleep(0.01)
        self.cache.payload = "new secret token cache"
        return self.result


def fixture_auth(tmp_path):
    store = FakeStore()
    store.payload = "cached account"
    cache = FakeCache()
    app = FakeApp(cache)
    calls = []

    def factory(client_id, **kwargs):
        calls.append((client_id, kwargs))
        return app

    module = SimpleNamespace(SerializableTokenCache=lambda: cache, PublicClientApplication=factory)
    auth = CalendarAuth(tmp_path, msal_module=module, store=store)
    return auth, app, cache, store, calls


def test_encrypted_token_store_never_writes_plaintext_and_round_trips(tmp_path):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    assert store.load() is None
    payload = '{"refresh_token":"highly-sensitive-refresh-secret"}'
    store.save(payload)
    assert payload.encode() not in store.path.read_bytes()
    assert b"highly-sensitive-refresh-secret" not in store.path.read_bytes()
    assert store.load() == payload
    assert list(store.path.parent.glob("*.tmp")) == []
    store.clear()
    assert not store.path.exists()


def test_atomic_save_failure_preserves_existing_encrypted_cache(tmp_path, monkeypatch):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    store.save("old token")
    previous = store.path.read_bytes()
    monkeypatch.setattr("services.calendar_auth.os.replace", lambda *args: (_ for _ in ()).throw(OSError("secret token path")))
    with pytest.raises(CalendarAuthError, match="could not be saved") as failure:
        store.save("new token")
    assert "secret token path" not in str(failure.value)
    assert store.path.read_bytes() == previous
    assert list(store.path.parent.glob("*.tmp")) == []


def test_cancel_during_encryption_never_replaces_existing_saved_account(tmp_path):
    cancel = threading.Event()

    class CancellingProtector(FakeProtector):
        should_cancel = False

        def protect(self, payload):
            blob = super().protect(payload)
            if self.should_cancel:
                cancel.set()
            return blob

    protector = CancellingProtector()
    store = EncryptedTokenStore(tmp_path, protector=protector)
    store.save("previous-account-token")
    previous = store.path.read_bytes()
    protector.should_cancel = True
    with pytest.raises(CalendarCancelled):
        store.save("new-account-token", cancel_event=cancel)
    assert store.path.read_bytes() == previous


@pytest.mark.parametrize("had_previous", [False, True])
def test_cancel_during_atomic_replace_restores_original_encrypted_state(tmp_path, monkeypatch, had_previous):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    if had_previous:
        store.save("previous-account-token")
    previous = store.path.read_bytes() if had_previous else None
    cancel = threading.Event()
    replace = os.replace
    calls = []

    def replace_then_cancel(source, destination):
        replace(source, destination)
        calls.append(destination)
        cancel.set()

    monkeypatch.setattr("services.calendar_auth.os.replace", replace_then_cancel)
    with pytest.raises(CalendarCancelled):
        store.save("new-account-token", cancel_event=cancel)
    if had_previous:
        assert store.path.read_bytes() == previous
        assert len(calls) == 3  # new ciphertext, protective marker, old ciphertext
    else:
        assert not store.path.exists()
    assert list(store.path.parent.glob("*.tmp")) == []


def test_disconnect_marker_blocks_saved_account_after_failed_ciphertext_deletion(tmp_path, monkeypatch):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    store.save("previous-saved-account")
    encrypted = store.path.read_bytes()
    unlink = Path.unlink

    def reject_cache_delete(path, *args, **kwargs):
        if path == store.path:
            raise PermissionError("sensitive OS path")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", reject_cache_delete)
    with pytest.raises(CalendarAuthError, match="could not be removed") as failure:
        store.clear()
    assert "sensitive" not in str(failure.value)
    assert store.path.read_bytes() == encrypted
    assert store.marker_path.exists()
    # The next application's new store must remain disconnected too.
    assert EncryptedTokenStore(tmp_path, protector=FakeProtector()).load() is None
    store.save("silent-refreshed-token")
    assert store.load() is None, "A silent refresh cannot remove the disconnect marker"
    store.save("explicitly-connected-token", connected=True)
    assert store.load() == "explicitly-connected-token"
    assert not store.marker_path.exists()


def test_cancelled_interactive_save_preserves_previous_disconnect_marker_and_ciphertext(tmp_path, monkeypatch):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    store.save("previous-saved-token")
    store.marker_path.write_bytes(b"disconnected\n")
    checkpoint = store.checkpoint()
    cancel = threading.Event()
    replace = os.replace

    def replace_then_cancel(source, destination):
        replace(source, destination)
        if destination == store.path:
            cancel.set()

    monkeypatch.setattr("services.calendar_auth.os.replace", replace_then_cancel)
    with pytest.raises(CalendarCancelled):
        store.save("new-connected-token", cancel_event=cancel, connected=True)
    assert store.checkpoint() == checkpoint
    assert store.load() is None


def test_plaintext_or_corrupt_cache_is_rejected(tmp_path):
    store = EncryptedTokenStore(tmp_path, protector=FakeProtector())
    store.path.parent.mkdir()
    store.path.write_text('{"refresh_token":"must not be accepted"}')
    with pytest.raises(CalendarAuthError, match="unreadable"):
        store.load()


def test_dpapi_current_user_scope_no_machine_scope_or_plaintext_fallback(monkeypatch):
    calls = []
    module = SimpleNamespace(
        CryptProtectData=lambda *args: calls.append(("protect", args)) or b"ciphertext",
        CryptUnprotectData=lambda *args: calls.append(("unprotect", args)) or ("description", b"cleartext"),
    )
    monkeypatch.setitem(sys.modules, "win32crypt", module)
    assert WindowsUserProtector.protect(b"cleartext") == b"ciphertext"
    assert WindowsUserProtector.unprotect(b"ciphertext") == b"cleartext"
    assert calls[0][1][-1] == 1  # UI_FORBIDDEN, no CRYPTPROTECT_LOCAL_MACHINE (4)
    assert calls[1][1][-1] == 1
    assert calls[0][1][2] == calls[1][1][1]  # bound entropy


def test_silent_signin_selects_exact_account_read_only_scopes_and_redacts_errors(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    app.accounts.insert(0, {"username": "another@example.test"})
    result = auth.get_token(CONFIG)
    assert result["accountEmail"] == CONFIG["accountEmail"]
    assert app.scopes == [list(CALENDAR_SCOPES)]
    assert all("Write" not in scope for scope in CALENDAR_SCOPES)
    assert calls[0][1]["authority"] == "https://login.microsoftonline.com/organizations"
    assert calls[0][1]["enable_pii_log"] is False
    assert calls[0][1]["timeout"] == 15
    app.result = {"error": "invalid_grant", "error_description": "secret raw HTTP account details"}
    with pytest.raises(CalendarAuthError) as failure:
        auth.get_token(CONFIG)
    assert "secret" not in str(failure.value)


def test_wrong_account_device_signin_restores_cache_and_never_persists(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    before = cache.serialize()
    app.result["id_token_claims"]["preferred_username"] = "different@example.test"
    challenges = []
    with pytest.raises(CalendarAuthError, match="differs"):
        auth.connect(CONFIG, challenges.append, threading.Event())
    assert cache.serialize() == before
    assert store.saved == []
    assert challenges[0] == {"user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 900, "accountEmail": CONFIG["accountEmail"]}
    assert app.initiate_kwargs["params"]["login_hint"] == CONFIG["accountEmail"]
    assert "login_hint" not in app.initiate_kwargs  # requests must not receive this as a kwarg


def test_device_polling_cancel_expires_flow_and_preserves_old_cache(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    app.block = True
    cancel = threading.Event()
    outcomes = []
    before = cache.serialize()

    def run():
        try:
            auth.connect(CONFIG, lambda challenge: None, cancel)
        except Exception as exc:
            outcomes.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    cancel.set()
    worker.join(timeout=2)
    assert not worker.is_alive(), "Cancellation must terminate sign-in polling promptly"
    assert isinstance(outcomes[0], CalendarCancelled)
    assert store.saved == []
    assert cache.serialize() == before


def test_successful_device_connect_persists_only_protected_store_and_disconnect_clears(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    token = auth.connect(CONFIG, lambda value: None, threading.Event())
    assert token["access_token"] == "secret-access-token"
    assert store.saved == ["new secret token cache"]
    auth.disconnect()
    assert store.cleared
    assert auth._cache is None and auth._app is None


def test_failed_disconnect_still_clears_in_memory_authentication(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    auth.get_token(CONFIG)

    def reject_clear():
        raise CalendarAuthError("The saved calendar sign-in could not be removed.")

    store.clear = reject_clear
    with pytest.raises(CalendarAuthError, match="could not be removed"):
        auth.disconnect()
    assert auth._cache is None and auth._app is None and auth._app_key is None


def test_no_saved_signin_or_disconnect_marker_never_constructs_microsoft_client(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    store.payload = None
    with pytest.raises(CalendarAuthError, match="Connect") as failure:
        auth.get_token(CONFIG)
    assert failure.value.state == "disconnected"
    assert calls == [], "Refresh must not contact Microsoft metadata without a saved sign-in"


def test_silent_refresh_cancel_after_store_returns_restores_old_saved_state(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    store.payload = "original-persisted-cache"
    cache.has_state_changed = True
    cancel = threading.Event()
    save = store.save

    def save_then_cancel(value, cancel_event=None, *, connected=False):
        save(value, cancel_event=cancel_event, connected=connected)
        cancel.set()

    store.save = save_then_cancel
    with pytest.raises(CalendarCancelled):
        auth.get_token(CONFIG, cancel)
    assert store.payload == "original-persisted-cache"
    assert cache.serialize() == "original-persisted-cache"


@pytest.mark.parametrize("had_previous", [False, True])
def test_connect_cancel_immediately_after_store_returns_restores_prior_persistence(tmp_path, had_previous):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    cancel = threading.Event()
    original_persisted = "persisted-original-token" if had_previous else None
    store.payload = original_persisted
    original_cache = cache.serialize()
    save = store.save

    def save_then_cancel(value, cancel_event=None, *, connected=False):
        save(value, cancel_event=cancel_event, connected=connected)
        cancel.set()

    store.save = save_then_cancel
    with pytest.raises(CalendarCancelled):
        auth.connect(CONFIG, lambda value: None, cancel)
    assert cache.serialize() == (original_persisted if had_previous else original_cache)
    assert store.payload == original_persisted


def test_silent_response_without_claims_is_bound_to_selected_cached_account(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    app.result = {"access_token": "secret"}
    assert auth.get_token(CONFIG)["accountEmail"] == CONFIG["accountEmail"]
    app.accounts = [{"username": "different@example.test"}]
    with pytest.raises(CalendarAuthError, match="Connect"):
        auth.get_token(CONFIG)


def test_unexpected_device_signin_url_is_never_shown(tmp_path):
    auth, app, cache, store, calls = fixture_auth(tmp_path)
    app.flow["verification_uri"] = "https://phishing.example.test/signin"
    challenges = []
    with pytest.raises(CalendarAuthError, match="unsupported device sign-in link"):
        auth.connect(CONFIG, challenges.append, threading.Event())
    assert challenges == [] and store.saved == []


@pytest.mark.parametrize("uri", [
    "https://login.microsoft.com/device",
    "https://microsoft.com/devicelogin",
    "https://www.microsoft.com/devicelogin",
])
def test_supported_device_signin_page_reaches_challenge_and_token_polling(tmp_path, uri):
    auth, app, _, store, _ = fixture_auth(tmp_path)
    app.flow["verification_uri"] = uri
    challenges, polled = [], []
    acquire = app.acquire_token_by_device_flow

    def poll(flow):
        polled.append(flow["verification_uri"])
        return acquire(flow)

    app.acquire_token_by_device_flow = poll
    assert auth.connect(CONFIG, challenges.append, threading.Event())["accountEmail"] == CONFIG["accountEmail"]
    assert challenges[0]["verification_uri"] == uri
    assert polled == [uri] and len(store.saved) == 1


@pytest.mark.parametrize("uri", [
    "http://login.microsoft.com/device", "https://login.microsoft.com/other",
    "https://login.microsoft.com/device?code=unexpected", "https://login.microsoft.com/device#unexpected",
    "https://user@login.microsoft.com/device", "https://login.microsoft.com:8443/device",
    "https://login.microsoft.com.evil.test/device", "https://evil.test/device",
    None, [],
])
def test_device_signin_rejects_modified_or_malformed_entry_pages_before_polling(tmp_path, uri):
    auth, app, cache, store, _ = fixture_auth(tmp_path)
    app.flow["verification_uri"] = uri
    original = cache.serialize()
    challenges = []
    app.acquire_token_by_device_flow = lambda flow: pytest.fail("Rejected URL must never start token polling")
    with pytest.raises(CalendarAuthError, match="unsupported device sign-in link"):
        auth.connect(CONFIG, challenges.append, threading.Event())
    assert not challenges and not store.saved and cache.serialize() == original


def test_actual_msal_device_flow_with_fresh_source_platform_namespace_never_uses_network(tmp_path):
    if importlib.util.find_spec("msal") is None:
        pytest.skip("MSAL runtime dependency is unavailable in this test interpreter")
    source_root = Path(__file__).resolve().parents[1] / "src" / "python"
    script = textwrap.dedent('''
        import sys, json
        from types import SimpleNamespace
        sys.path.insert(0, sys.argv[1])
        import platform
        assert platform.__file__.replace("\\\\", "/").endswith("/src/python/platform/__init__.py")
        assert not hasattr(platform, "system")
        import platform.win_constants
        import msal
        from services.calendar_auth import CalendarAuth, CalendarAuthError
        class Response:
            status_code = 200
            headers = {}
            def __init__(self, value):
                self.text = json.dumps(value)
            def json(self):
                return json.loads(self.text)
        class Http:
            def __init__(self):
                self.calls = []
            def get(self, url, **kwargs):
                self.calls.append("metadata")
                assert url.endswith("/v2.0/.well-known/openid-configuration")
                return Response({
                    "authorization_endpoint": "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize",
                    "token_endpoint": "https://login.microsoftonline.com/organizations/oauth2/v2.0/token",
                    "device_authorization_endpoint": "https://login.microsoftonline.com/organizations/oauth2/v2.0/devicecode",
                    "issuer": "https://login.microsoftonline.com/organizations/v2.0",
                })
            def post(self, url, **kwargs):
                if url.endswith("/devicecode"):
                    self.calls.append("devicecode")
                    assert kwargs["params"]["login_hint"] == "synthetic@example.test"
                    assert set(kwargs["data"]["scope"].split()) == {"Calendars.Read", "Calendars.Read.Shared", "openid", "profile", "offline_access"}
                    return Response({"device_code": "SYNTHETIC-DEVICE-CODE", "user_code": "SYNTHETIC", "verification_uri": "https://login.microsoft.com/device", "expires_in": 900})
                assert url.endswith("/token")
                self.calls.append("token")
                return Response({"error": "authorization_declined", "error_description": "SYNTHETIC RAW RESPONSE MUST NOT ESCAPE"})
        http = Http()
        def application(client_id, **kwargs):
            return msal.PublicClientApplication(client_id, http_client=http, instance_discovery=False, **kwargs)
        module = SimpleNamespace(SerializableTokenCache=msal.SerializableTokenCache, PublicClientApplication=application)
        class Store:
            def load(self):
                return None
            def checkpoint(self):
                return (None, None)
            def save(self, value, cancel_event=None, *, connected=False):
                raise AssertionError("Declined sign-in must never be saved")
        auth = CalendarAuth(sys.argv[2], msal_module=module, store=Store())
        challenges = []
        try:
            auth.connect({"clientId": "d1234567-1234-1234-1234-123456789abc", "tenantId": "organizations", "accountEmail": "synthetic@example.test"}, challenges.append, None)
            raise AssertionError("Expected declined fixture result")
        except CalendarAuthError as failure:
            assert str(failure) == "Microsoft sign-in was declined."
        assert len(challenges) == 1 and "device_code" not in challenges[0]
        assert http.calls == ["metadata", "devicecode", "token"]
        assert hasattr(platform, "__path__") and platform.win_constants.WM_KEYDOWN == 0x0100
        print("Real MSAL fake-HTTP source-platform namespace passed")
    ''')
    result = subprocess.run(
        [sys.executable, "-c", script, str(source_root), str(tmp_path)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source-platform namespace passed" in result.stdout
