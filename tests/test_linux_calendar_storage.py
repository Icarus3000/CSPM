"""Linux calendar persistence is authenticated, wallet-bound and fail-closed."""
from __future__ import annotations

from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/python"))

from services import calendar_auth
from services.calendar_auth import (
    CalendarAuthError, CalendarCancelled, EncryptedTokenStore,
    LinuxSecretServiceProtector, WindowsUserProtector,
)


class Wallet:
    collection_path = "/org/freedesktop/secrets/collection/default"

    def __init__(self):
        self.items = {}
        self.locked = False
        self.connections_closed = 0

    def dbus_init(self):
        return SimpleNamespace(close=lambda: setattr(self, "connections_closed", self.connections_closed + 1))

    def get_collection_by_alias(self, _connection, alias):
        assert alias == "default"
        return self

    def ensure_not_locked(self):
        if self.locked:
            raise RuntimeError("private backend detail must not escape")

    def search_items(self, attributes):
        key = tuple(sorted(attributes.items()))
        if key not in self.items:
            return []
        return [SimpleNamespace(get_secret=lambda: self.items[key])]

    def create_item(self, label, attributes, secret, **kwargs):
        assert kwargs == {"replace": False, "content_type": "application/octet-stream"}
        assert "token" not in label.lower()
        self.items[tuple(sorted(attributes.items()))] = secret


def store_for(profile, wallet, monkeypatch):
    constructor = LinuxSecretServiceProtector
    monkeypatch.setattr(calendar_auth, "LinuxSecretServiceProtector",
                        lambda path: constructor(path, secret_module=wallet))
    return EncryptedTokenStore(profile)


def test_actual_fernet_roundtrip_restart_and_no_plaintext(tmp_path, monkeypatch):
    wallet = Wallet()
    store = store_for(tmp_path, wallet, monkeypatch)
    payload = '{"refresh_token":"synthetic-secret-for-fixture"}'
    store.save(payload, connected=True)
    blob = store.path.read_bytes()
    assert store.path.name == "token_cache.secretservice"
    assert payload.encode() not in blob
    assert b"synthetic-secret-for-fixture" not in blob
    assert store.load() == payload
    assert EncryptedTokenStore(tmp_path).load() == payload
    assert len(wallet.items) == 1
    assert all(secret != payload.encode() for secret in wallet.items.values())
    assert wallet.connections_closed == 3
    store.clear()
    assert store.load() is None


@pytest.mark.parametrize("failure", ["locked", "missing", "session"])
def test_unavailable_or_unsafe_wallet_cannot_write_a_token(tmp_path, monkeypatch, failure):
    wallet = Wallet()
    if failure == "locked":
        wallet.locked = True
    elif failure == "session":
        wallet.collection_path = "/org/freedesktop/secrets/collection/session"
    else:
        wallet.get_collection_by_alias = lambda *_: (_ for _ in ()).throw(RuntimeError("private error"))
    store = store_for(tmp_path, wallet, monkeypatch)
    with pytest.raises(CalendarAuthError, match="desktop wallet") as result:
        store.save("must not reach disk")
    assert "private" not in str(result.value)
    assert not store.path.exists()
    assert not wallet.items
    assert wallet.connections_closed == 1


def test_changed_wallet_and_tampered_ciphertext_are_rejected(tmp_path, monkeypatch):
    wallet = Wallet()
    store = store_for(tmp_path, wallet, monkeypatch)
    store.save("sensitive fixture")
    encrypted = store.path.read_bytes()
    store.path.write_bytes(encrypted[:-2] + b"??")
    with pytest.raises(CalendarAuthError):
        store.load()
    store.path.write_bytes(encrypted)
    wallet.items.clear()
    with pytest.raises(CalendarAuthError):
        store.load()
    assert not wallet.items, "loading must never replace a missing encryption key"


def test_profile_keys_are_separate_and_do_not_expose_paths(tmp_path):
    wallet = Wallet()
    a = LinuxSecretServiceProtector(tmp_path / "a", secret_module=wallet)
    b = LinuxSecretServiceProtector(tmp_path / "b", secret_module=wallet)
    token = a.protect(b"fixture")
    with pytest.raises(CalendarAuthError):
        b.unprotect(token)
    assert len(wallet.items) == 1
    assert str(tmp_path) not in repr(wallet.items)


def test_cancellation_restores_ciphertext_and_disconnect_survives_refresh(tmp_path, monkeypatch):
    wallet = Wallet()
    store = store_for(tmp_path, wallet, monkeypatch)
    store.save("original", connected=True)
    original = store.checkpoint()
    cancel = threading.Event()
    replace = calendar_auth.os.replace

    def replace_then_cancel(source, target):
        replace(source, target)
        cancel.set()

    monkeypatch.setattr(calendar_auth.os, "replace", replace_then_cancel)
    with pytest.raises(CalendarCancelled):
        store.save("cancelled", cancel, connected=True)
    assert store.checkpoint() == original
    monkeypatch.setattr(calendar_auth.os, "replace", replace)
    store.clear()
    store.save("background-refresh")
    assert EncryptedTokenStore(tmp_path).load() is None
    store.save("new-explicit-signin", connected=True)
    assert store.load() == "new-explicit-signin"


def test_windows_keeps_the_existing_dpapi_path(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_auth.sys, "platform", "win32")
    store = EncryptedTokenStore(tmp_path)
    assert isinstance(store.protector, WindowsUserProtector)
    assert store.path.name == "token_cache.dpapi"
    assert store._header == calendar_auth._CACHE_HEADER
