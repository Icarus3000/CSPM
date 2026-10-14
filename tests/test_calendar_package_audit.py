"""A public CA bundle exception must not allow private PEM material."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


AUDIT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "diagnostics" / "audit_lifecycle_package.py"
SPEC = importlib.util.spec_from_file_location("calendar_package_audit_test", AUDIT_PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

PUBLIC_CERTIFICATE = b"-----BEGIN CERTIFICATE-----\nU1lOVEhFVElD\n-----END CERTIFICATE-----\n"
PIN = b"certifi==2026.7.22\n"


def fixture_bundle(tmp_path, *, canonical=PUBLIC_CERTIFICATE, packaged=PUBLIC_CERTIFICATE,
                   version="2026.7.22"):
    canonical_path = tmp_path / "dependency" / "certifi" / "cacert.pem"
    packaged_path = tmp_path / "package" / "certifi" / "cacert.pem"
    canonical_path.parent.mkdir(parents=True)
    packaged_path.parent.mkdir(parents=True)
    canonical_path.write_bytes(canonical)
    packaged_path.write_bytes(packaged)
    lookup = lambda name: SimpleNamespace(version=version, locate_file=lambda relative: canonical_path)
    return packaged_path, lookup


def test_exact_pinned_canonical_certifi_bundle_is_allowed(tmp_path):
    path, lookup = fixture_bundle(tmp_path)
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN, distribution_lookup=lookup,
    )
    assert result["allowed"] is True
    assert result["pinnedVersion"] == result["installedVersion"] == "2026.7.22"
    assert result["sha256"] == result["canonicalSha256"] == AUDIT.sha(path)
    assert result["certificateCount"] == 1


def test_changed_certificate_bytes_remain_a_private_artifact(tmp_path):
    path, lookup = fixture_bundle(tmp_path, packaged=PUBLIC_CERTIFICATE + b"changed\n")
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN, distribution_lookup=lookup,
    )
    assert not result["allowed"] and result["sha256"] != result["canonicalSha256"]


@pytest.mark.parametrize("relative", [
    "_internal/certifi/other.pem", "_internal/user/cacert.pem", "certifi/cacert.pem",
    "_internal/certifi/private.pem", "_internal/certifi/CACERT.PEM",
])
def test_all_other_pem_locations_remain_rejected(tmp_path, relative):
    path, lookup = fixture_bundle(tmp_path)
    result = AUDIT.validate_public_trust_bundle(relative, path, PIN, distribution_lookup=lookup)
    assert result["allowed"] is False and result["installedVersion"] is None


@pytest.mark.parametrize("body", [
    # Construct synthetic markers so the staged-source credential scanner
    # does not mistake this negative fixture for actual private-key material.
    PUBLIC_CERTIFICATE + b"-----BEGIN " + b"PRIVATE KEY-----\nPRIVATE\n-----END " + b"PRIVATE KEY-----\n",
    PUBLIC_CERTIFICATE + b"-----BEGIN " + b"RSA PRIVATE KEY-----\nPRIVATE\n-----END " + b"RSA PRIVATE KEY-----\n",
    PUBLIC_CERTIFICATE + b"private_key = synthetic\n",
    b"-----BEGIN PUBLIC KEY-----\nSYNTHETIC\n-----END PUBLIC KEY-----\n",
    b"not a PEM certificate\n", b"-----BEGIN CERTIFICATE-----\nunclosed\n",
])
def test_private_key_or_noncertificate_payload_rejected_even_if_canonical_matches(tmp_path, body):
    path, lookup = fixture_bundle(tmp_path, canonical=body, packaged=body)
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN, distribution_lookup=lookup,
    )
    assert result["sha256"] == result["canonicalSha256"]
    assert result["allowed"] is False


@pytest.mark.parametrize("requirements", [b"", b"certifi>=2026.7.22\n", b"other==1.0\n",
                                          b"certifi==2026.7.22\ncertifi==2026.7.22\n"])
def test_missing_or_unpinned_immutable_dependency_remains_rejected(tmp_path, requirements):
    path, lookup = fixture_bundle(tmp_path)
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, requirements, distribution_lookup=lookup,
    )
    assert result["allowed"] is False and result["pinnedVersion"] is None


def test_different_installed_version_cannot_authorize_bundle(tmp_path):
    path, lookup = fixture_bundle(tmp_path, version="2025.1.1")
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN, distribution_lookup=lookup,
    )
    assert result["allowed"] is False and result["installedVersion"] == "2025.1.1"


def test_missing_pinned_installation_or_bundle_remains_rejected(tmp_path):
    path, _ = fixture_bundle(tmp_path)

    def missing_dependency(name):
        raise ModuleNotFoundError("synthetic missing dependency")

    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN, distribution_lookup=missing_dependency,
    )
    assert not result["allowed"]
    result = AUDIT.validate_public_trust_bundle(
        "_internal/certifi/cacert.pem", path, PIN,
        distribution_lookup=lambda name: SimpleNamespace(version="2026.7.22", locate_file=lambda value: tmp_path / "missing.pem"),
    )
    assert not result["allowed"]
