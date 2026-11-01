"""Unit tests for Quick Expense Web Push (RFC 8292 VAPID + RFC 8291 aes128gcm)."""
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

# Add src/python to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = REPO_ROOT / "src" / "python"
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from services.quick_expense_push import (
    PushManager,
    _b64url_decode,
    _b64url_encode,
    get_push_manager,
    get_vapid_public_key,
    subscribe,
    unsubscribe,
)


class TestQuickExpensePush(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name) / "push_test_state.json"
        self.mgr = PushManager(storage_path=self.storage_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_vapid_key_generation_and_persistence(self) -> None:
        pub_key_b64 = self.mgr.get_public_key()
        self.assertTrue(bool(pub_key_b64))

        pub_bytes = _b64url_decode(pub_key_b64)
        self.assertEqual(len(pub_bytes), 65)
        self.assertEqual(pub_bytes[0], 4)  # Uncompressed P-256 curve point

        # Reload from disk and verify persistence
        mgr2 = PushManager(storage_path=self.storage_path)
        self.assertEqual(mgr2.get_public_key(), pub_key_b64)

    def test_vapid_jwt_es256_signature_verification(self) -> None:
        endpoint = "https://fcm.googleapis.com/fcm/send/fake-device-token-123"
        header = self.mgr.create_vapid_auth_header(endpoint)
        self.assertTrue(header.startswith("vapid "))

        # Extract t=<jwt>, k=<pub>
        parts = dict(kv.split("=", 1) for kv in header[6:].split(", "))
        jwt_token = parts["t"]
        k_pub = parts["k"]

        self.assertEqual(k_pub, self.mgr.get_public_key())

        jwt_parts = jwt_token.split(".")
        self.assertEqual(len(jwt_parts), 3)

        header_bytes = _b64url_decode(jwt_parts[0])
        claims_bytes = _b64url_decode(jwt_parts[1])
        raw_sig = _b64url_decode(jwt_parts[2])

        self.assertEqual(len(raw_sig), 64)

        header_data = json.loads(header_bytes.decode("utf-8"))
        self.assertEqual(header_data.get("alg"), "ES256")
        self.assertEqual(header_data.get("typ"), "JWT")

        claims_data = json.loads(claims_bytes.decode("utf-8"))
        self.assertEqual(claims_data.get("aud"), "https://fcm.googleapis.com")
        self.assertTrue(claims_data.get("exp") > 0)
        self.assertEqual(claims_data.get("sub"), "mailto:cory@coryschneiderlaw.ca")

        # Verify signature with the public key
        pub_key_bytes = _b64url_decode(k_pub)
        pub_ec = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_key_bytes)

        r = int.from_bytes(raw_sig[:32], "big")
        s = int.from_bytes(raw_sig[32:], "big")
        der_sig = utils.encode_dss_signature(r, s)

        signing_input = f"{jwt_parts[0]}.{jwt_parts[1]}".encode("ascii")
        pub_ec.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))

    def test_rfc8291_aes128gcm_roundtrip(self) -> None:
        # Simulate browser / client device keypair
        ua_priv = ec.generate_private_key(ec.SECP256R1())
        ua_pub_bytes = ua_priv.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        ua_auth_bytes = os.urandom(16)

        ua_pub_b64 = _b64url_encode(ua_pub_bytes)
        ua_auth_b64 = _b64url_encode(ua_auth_bytes)

        test_payload = json.dumps({"title": "Test Title", "body": "Test Body", "amount": 142.50}).encode("utf-8")

        # 1. Server Encrypts
        encrypted_body = PushManager.encrypt_payload(
            payload=test_payload,
            ua_pub_b64=ua_pub_b64,
            auth_b64=ua_auth_b64,
        )

        # Header check: salt(16) + rs(4) + idlen(1) + as_pub(65) = 86 bytes
        self.assertGreater(len(encrypted_body), 86)
        salt = encrypted_body[:16]
        rs = struct.unpack(">I", encrypted_body[16:20])[0]
        idlen = encrypted_body[20]
        as_pub_bytes = encrypted_body[21:21 + idlen]
        ciphertext = encrypted_body[21 + idlen:]

        self.assertEqual(rs, 4096)
        self.assertEqual(idlen, 65)
        self.assertEqual(len(as_pub_bytes), 65)

        # 2. Client Decrypts (simulating browser Web Push receiver)
        as_pub_ec = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub_bytes)
        ecdh_secret = ua_priv.exchange(ec.ECDH(), as_pub_ec)

        auth_info = b"WebPush: info\x00" + ua_pub_bytes + as_pub_bytes
        prk = HKDF(hashes.SHA256(), length=32, salt=ua_auth_bytes, info=auth_info).derive(ecdh_secret)
        cek = HKDF(hashes.SHA256(), length=16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(prk)
        nonce = HKDF(hashes.SHA256(), length=12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(prk)

        decrypted_padded = AESGCM(cek).decrypt(nonce, ciphertext, b"")
        delimiter_idx = decrypted_padded.rfind(b"\x02")
        self.assertNotEqual(delimiter_idx, -1)
        decrypted_plaintext = decrypted_padded[:delimiter_idx]

        self.assertEqual(decrypted_plaintext, test_payload)

    def test_subscribe_and_unsubscribe_lifecycle(self) -> None:
        sub_data = {
            "endpoint": "https://push.services.mozilla.com/v1/test-device",
            "keys": {
                "p256dh": "dummy-p256dh-key",
                "auth": "dummy-auth-key",
            },
        }
        res = self.mgr.subscribe(sub_data, username="deborah", platform="Android")
        self.assertTrue(res.get("ok"))
        self.assertEqual(len(self.mgr.list_subscriptions()), 1)

        subs = self.mgr.list_subscriptions(target_username="deborah")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["username"], "deborah")

        subs_cory = self.mgr.list_subscriptions(target_username="cory")
        self.assertEqual(len(subs_cory), 0)

        unsub_res = self.mgr.unsubscribe("https://push.services.mozilla.com/v1/test-device")
        self.assertTrue(unsub_res.get("ok"))
        self.assertEqual(unsub_res.get("removed"), 1)
        self.assertEqual(len(self.mgr.list_subscriptions()), 0)


if __name__ == "__main__":
    unittest.main()
