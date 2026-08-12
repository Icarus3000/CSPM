"""Conflict-safe synchronization of CSPM's cloud authority and local replica.

The shared folder is the canonical data source.  A machine's local folder is
only a working replica.  Synchronization therefore compares every workbook to
the last known common hash rather than trusting filesystem timestamps:

* cloud-only change -> pull cloud into the local replica;
* local-only change -> push known offline work to cloud;
* both changed -> preserve both files and report a conflict, never overwrite.

Both governed workbooks are treated as one synchronization unit, preventing a
partial CSPM/Dockets update from creating a mixed financial dataset.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from services.paths import AppPaths


logger = logging.getLogger("sync_service")


class SyncService:
    """Synchronize the canonical shared package with one checked-out replica.

    CSPM's macro workbooks cannot safely co-author financial writes.  A shared
    folder is therefore used as a one-writer source, not as two independent
    local sources.  ``checkout_from_cloud`` obtains the shared write lease
    before a local replica is made writable; ``publish_and_release`` creates a
    verified immutable release before promoting the local package to cloud.

    The lease is intentionally conservative.  It never expires automatically:
    a crashed or abandoned checkout needs an explicit recovery decision rather
    than risking a second computer overwriting in-progress work.
    """

    STATE_VERSION = 2
    BLANK_SEED_MAX_BYTES = 50_000
    _FILES = ("CSPM.xlsm", "Dockets.xlsm")
    LEASE_FILE_NAME = ".cspm_checkout.json"
    RELEASES_DIR_NAME = ".cspm_releases"
    RELEASE_MANIFEST_NAME = "release.json"
    MACHINE_ID_FILE_NAME = "cloud_checkout_machine.json"

    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.state_file = self.paths.runtime_dir() / "sync_state.json"
        self._checkout_id = uuid4().hex
        self._machine_id: Optional[str] = None
        self._lease_owned = False
        self._shutdown_complete = False

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().upper()

    @staticmethod
    def _usable(path: Path) -> bool:
        try:
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    def _is_blank_seed(self, file_name: str, path: Path) -> bool:
        """Recognize only the small generated CSPM seed as an empty replica."""
        if file_name != "CSPM.xlsm" or not self._usable(path):
            return False
        try:
            return path.stat().st_size < self.BLANK_SEED_MAX_BYTES
        except OSError:
            return False

    def _empty_state(self) -> Dict[str, Any]:
        return {"version": self.STATE_VERSION, "files": {}}

    def _get_state(self) -> Dict[str, Any]:
        if not self.state_file.is_file():
            return self._empty_state()
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return self._empty_state()
            files = raw.get("files")
            if not isinstance(files, dict):
                # A timestamp-only legacy state is deliberately not trusted
                # as a common ancestor.  If files differ, a safe conflict is
                # preferable to silently choosing the machine that ran last.
                return self._empty_state()
            return {"version": self.STATE_VERSION, "files": dict(files)}
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("SyncService: could not read sync state %s: %s", self.state_file, exc)
            return self._empty_state()

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.STATE_VERSION,
            "files": state.get("files", {}),
            "updatedAtUtc": datetime.now(UTC).isoformat(),
        }
        temporary = self.state_file.with_name(f".{self.state_file.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(temporary, self.state_file)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        try:
            return left.resolve() == right.resolve()
        except OSError:
            return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))

    def _machine_identity(self) -> str:
        """Return the durable ID for this CSPM installation, not a username."""
        if self._machine_id:
            return self._machine_id
        identity_file = self.paths.runtime_dir() / self.MACHINE_ID_FILE_NAME
        try:
            if identity_file.is_file():
                raw = json.loads(identity_file.read_text(encoding="utf-8"))
                candidate = str(raw.get("machineId", "")).strip() if isinstance(raw, dict) else ""
                if candidate:
                    self._machine_id = candidate
                    return candidate
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("SyncService: could not read machine identity: %s", exc)

        self._machine_id = uuid4().hex
        identity_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = identity_file.with_name(f".{identity_file.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps({"machineId": self._machine_id}, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, identity_file)
        finally:
            temporary.unlink(missing_ok=True)
        return self._machine_id

    def _lease_path(self) -> Optional[Path]:
        master_dir = self.paths.master_data_dir()
        return master_dir / self.LEASE_FILE_NAME if master_dir else None

    def _read_lease(self) -> Dict[str, Any]:
        lease_path = self._lease_path()
        if not lease_path or not lease_path.is_file():
            return {}
        try:
            raw = json.loads(lease_path.read_text(encoding="utf-8"))
            return dict(raw) if isinstance(raw, dict) else {}
        except (OSError, ValueError, TypeError) as exc:
            logger.error("SyncService: shared checkout marker is unreadable: %s", exc)
            return {"unreadable": True}

    def _lease_matches_self(self, lease: Dict[str, Any]) -> bool:
        return (
            bool(lease)
            and lease.get("machineId") == self._machine_identity()
            and lease.get("checkoutId") == self._checkout_id
            and int(lease.get("processId", 0) or 0) == os.getpid()
        )

    def _lease_payload(self) -> Dict[str, Any]:
        return {
            "schemaVersion": 1,
            "machineId": self._machine_identity(),
            "checkoutId": self._checkout_id,
            "processId": os.getpid(),
            "computerName": socket.gethostname(),
            "checkedOutAtUtc": datetime.now(UTC).isoformat(),
            "purpose": "CSPM exclusive workbook write checkout",
        }

    @staticmethod
    def _lease_description(lease: Dict[str, Any]) -> str:
        if not lease:
            return "another CSPM session"
        if lease.get("unreadable"):
            return "an unreadable shared checkout marker"
        computer = str(lease.get("computerName", "another computer") or "another computer")
        checked_out = str(lease.get("checkedOutAtUtc", "an unknown time") or "an unknown time")
        return f"{computer} since {checked_out}"

    def _acquire_checkout_lease(self) -> Dict[str, Any]:
        """Atomically create the shared one-writer marker when possible."""
        lease_path = self._lease_path()
        if lease_path is None:
            self._lease_owned = True
            return self._result(True, "local-only", "No shared cloud folder is configured.")
        lease_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_lease()
        if self._lease_matches_self(existing):
            self._lease_owned = True
            return self._result(True, "checked-out", "This CSPM session already holds the shared write checkout.")
        if existing:
            return self._result(
                False,
                "checkout-held",
                f"Shared data is checked out by {self._lease_description(existing)}. This session is read-only.",
                lease=existing,
            )

        payload = self._lease_payload()
        try:
            # Exclusive create is deliberate: do not use an overwrite/replace
            # operation for a checkout marker that may belong to another PC.
            with lease_path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            self._lease_owned = True
            return self._result(True, "checked-out", "Exclusive shared write checkout acquired.", lease=payload)
        except FileExistsError:
            existing = self._read_lease()
            return self._result(
                False,
                "checkout-held",
                f"Shared data is checked out by {self._lease_description(existing)}. This session is read-only.",
                lease=existing,
            )
        except OSError as exc:
            return self._result(False, "checkout-error", f"Could not acquire the shared write checkout: {exc}")

    def _release_checkout_lease(self) -> Dict[str, Any]:
        """Release only this process's lease; never remove another computer's."""
        lease_path = self._lease_path()
        if lease_path is None:
            self._lease_owned = False
            return self._result(True, "released", "Local-only session ended.")
        lease = self._read_lease()
        if not self._lease_matches_self(lease):
            self._lease_owned = False
            if not lease:
                return self._result(True, "released", "No shared checkout marker remained.")
            return self._result(
                False,
                "lease-changed",
                "The shared checkout marker changed ownership; it was not removed.",
                lease=lease,
            )
        try:
            lease_path.unlink()
            self._lease_owned = False
            return self._result(True, "released", "Shared write checkout released.")
        except OSError as exc:
            return self._result(False, "release-error", f"Could not release the shared checkout: {exc}")

    def assert_write_lease(self) -> None:
        """Raise before any local workbook save if this session is read-only."""
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            return
        lease = self._read_lease()
        if self._lease_owned and self._lease_matches_self(lease):
            return
        raise PermissionError(
            "CSPM cannot save because this local copy is read-only. "
            "Check out the shared data from the cloud before making financial or practice-data changes."
        )

    @staticmethod
    def _result(ok: bool, status: str, message: str, **extra: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": ok, "status": status, "message": message}
        result.update(extra)
        return result

    def _recovery_copy(self, destination: Path, reason: str) -> Optional[Path]:
        if not self._usable(destination):
            return None
        recovery_dir = destination.parent / "sync_recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = recovery_dir / (
            f"{destination.stem}_{reason}_{stamp}_{uuid4().hex[:8]}{destination.suffix}"
        )
        shutil.copy2(destination, backup)
        if self._sha256(destination) != self._sha256(backup):
            backup.unlink(missing_ok=True)
            raise RuntimeError(f"Recovery copy verification failed for {destination.name}.")
        return backup

    def _copy_verified(self, source: Path, destination: Path, reason: str) -> Optional[Path]:
        """Copy beside the target, verify content, then atomically promote it."""
        if not self._usable(source):
            raise FileNotFoundError(f"Sync source is missing or empty: {source}")
        source_hash = self._sha256(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = self._recovery_copy(destination, reason)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.sync-tmp")
        try:
            shutil.copy2(source, temporary)
            if self._sha256(temporary) != source_hash:
                raise RuntimeError(f"Checksum mismatch while synchronizing {destination.name}.")
            os.replace(temporary, destination)
            if self._sha256(destination) != source_hash:
                raise RuntimeError(f"Post-copy checksum mismatch for {destination.name}.")
        finally:
            temporary.unlink(missing_ok=True)
        return backup

    def _package_paths(self, directory: Path) -> Dict[str, Path]:
        return {name: directory / name for name in self._FILES}

    @staticmethod
    def _set_base_hashes(state: Dict[str, Any], hashes: Dict[str, str]) -> None:
        files = state.setdefault("files", {})
        for name, file_hash in hashes.items():
            files[name] = {
                "baseHash": file_hash,
                "lastSynchronizedAtUtc": datetime.now(UTC).isoformat(),
            }

    def _create_release(self, source_paths: Dict[str, Path], reason: str) -> Dict[str, Any]:
        """Persist a complete verified cloud-side release before root promotion."""
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            raise RuntimeError("Cannot create a cloud release without a shared data folder.")
        release_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{self._machine_identity()[:8]}_{uuid4().hex[:8]}"
        release_dir = master_dir / self.RELEASES_DIR_NAME / release_id
        release_dir.mkdir(parents=True, exist_ok=False)
        hashes: Dict[str, str] = {}
        try:
            for name in self._FILES:
                self._copy_verified(source_paths[name], release_dir / name, "before_release_write")
                hashes[name] = self._sha256(release_dir / name)
            manifest = {
                "schemaVersion": 1,
                "releaseId": release_id,
                "createdAtUtc": datetime.now(UTC).isoformat(),
                "machineId": self._machine_identity(),
                "reason": reason,
                "files": hashes,
            }
            manifest_path = release_dir / self.RELEASE_MANIFEST_NAME
            temporary = manifest_path.with_name(f".{manifest_path.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
                os.replace(temporary, manifest_path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"releaseId": release_id, "releasePath": str(release_dir), "hashes": hashes}
        except Exception:
            # Keep an incomplete candidate for diagnosis, but never claim it
            # is a release because it has no final manifest.
            logger.exception("SyncService could not create cloud release candidate %s", release_dir)
            raise

    def _synchronize(self, phase: str, *, create_release: bool = False) -> Dict[str, Any]:
        """Safely reconcile both governed files using their common ancestor."""
        master_dir = self.paths.master_data_dir()
        local_dir = self.paths.data_dir()
        if not master_dir:
            return self._result(True, "disabled", "No shared cloud data folder is configured.")
        if self._same_path(master_dir, local_dir):
            return self._result(
                True,
                "same-folder",
                "Shared and local folders are the same; no replica synchronization was run.",
            )

        cloud_paths = self._package_paths(master_dir)
        local_paths = self._package_paths(local_dir)
        missing_cloud = [name for name, path in cloud_paths.items() if not self._usable(path)]
        if missing_cloud:
            return self._result(
                False,
                "cloud-missing",
                "Shared cloud package is incomplete; no local data was copied.",
                missingFiles=missing_cloud,
            )

        state = self._get_state()
        records: Dict[str, Dict[str, Any]] = {}
        local_package_blank = (
            not self._usable(local_paths["CSPM.xlsm"])
            or self._is_blank_seed("CSPM.xlsm", local_paths["CSPM.xlsm"])
        )
        for name in self._FILES:
            cloud_hash = self._sha256(cloud_paths[name])
            local_path = local_paths[name]
            # The generated empty CSPM package contains a small CSPM workbook
            # plus a template Dockets workbook.  Treat that entire pair as an
            # empty replica so a fresh machine pulls the cloud package rather
            # than falsely treating its template Dockets file as offline work.
            local_is_blank = local_package_blank or not self._usable(local_path)
            local_hash = "" if local_is_blank else self._sha256(local_path)
            saved = state.get("files", {}).get(name, {})
            base_hash = str(saved.get("baseHash", "")) if isinstance(saved, dict) else ""
            records[name] = {
                "cloudHash": cloud_hash,
                "localHash": local_hash,
                "baseHash": base_hash,
                "localBlank": local_is_blank,
            }

        unknown_divergence = [
            name
            for name, record in records.items()
            if not record["localBlank"]
            and record["localHash"] != record["cloudHash"]
            and not record["baseHash"]
        ]
        if unknown_divergence:
            return self._result(
                False,
                "conflict",
                "Local and cloud copies differ without a recorded common ancestor; neither copy was overwritten.",
                phase=phase,
                files=unknown_divergence,
            )

        local_only_changes = []
        cloud_only_changes = []
        both_changed = []
        for name, record in records.items():
            if record["localBlank"]:
                cloud_only_changes.append(name)
                continue
            if record["localHash"] == record["cloudHash"]:
                continue
            base_hash = record["baseHash"]
            local_changed = record["localHash"] != base_hash
            cloud_changed = record["cloudHash"] != base_hash
            if local_changed and cloud_changed:
                both_changed.append(name)
            elif local_changed:
                local_only_changes.append(name)
            elif cloud_changed:
                cloud_only_changes.append(name)
            else:
                both_changed.append(name)

        if both_changed or (local_only_changes and cloud_only_changes) or (
            any(record["localBlank"] for record in records.values()) and local_only_changes
        ) or (phase == "publish" and cloud_only_changes):
            return self._result(
                False,
                "conflict",
                "Both the local replica and cloud authority changed; neither copy was overwritten.",
                phase=phase,
                files=sorted(set(both_changed + local_only_changes + cloud_only_changes)),
            )

        try:
            backups: Dict[str, str] = {}
            release: Optional[Dict[str, Any]] = None
            if local_only_changes:
                direction = "push"
                source_paths = local_paths
                destination_paths = cloud_paths
                reason = "before_cloud_push"
                if create_release:
                    release = self._create_release(source_paths, "publish")
            elif cloud_only_changes:
                direction = "pull"
                source_paths = cloud_paths
                destination_paths = local_paths
                reason = "before_local_pull"
            else:
                hashes = {name: records[name]["cloudHash"] for name in self._FILES}
                self._set_base_hashes(state, hashes)
                self._save_state(state)
                return self._result(True, "unchanged", "Cloud authority and local replica already match.", phase=phase)

            for name in self._FILES:
                source_hash = self._sha256(source_paths[name])
                destination_hash = self._sha256(destination_paths[name]) if self._usable(destination_paths[name]) else ""
                if source_hash == destination_hash:
                    continue
                backup = self._copy_verified(source_paths[name], destination_paths[name], reason)
                if backup:
                    backups[name] = str(backup)

            hashes = {name: self._sha256(source_paths[name]) for name in self._FILES}
            self._set_base_hashes(state, hashes)
            self._save_state(state)
            verb = "pushed to cloud" if direction == "push" else "pulled from cloud"
            logger.info("SyncService: %s package %s during %s.", direction, list(hashes), phase)
            return self._result(
                True,
                direction,
                f"Governed workbook package {verb} safely.",
                phase=phase,
                recoveryCopies=backups,
                release=release,
            )
        except Exception as exc:
            logger.exception("SyncService %s failed", phase)
            return self._result(False, "error", f"Synchronization failed without completing promotion: {exc}", phase=phase)

    def initialize_shared_source(self, seed_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Configure a cloud authority without ever replacing an existing one.

        A seed directory is used only if the configured shared folder has no
        usable package.  If the cloud already contains data, it remains the
        authority and this method delegates to conflict-safe synchronization.
        """
        master_dir = self.paths.master_data_dir()
        local_dir = self.paths.data_dir()
        if not master_dir:
            return self._result(False, "cloud-missing", "Choose a shared cloud data folder first.")
        if self._same_path(master_dir, local_dir):
            return self._result(False, "same-folder", "Shared and local folders must be different locations.")

        cloud_paths = self._package_paths(master_dir)
        usable_cloud = {name: self._usable(path) for name, path in cloud_paths.items()}
        if any(usable_cloud.values()) and not all(usable_cloud.values()):
            return self._result(
                False,
                "cloud-incomplete",
                "Shared folder contains an incomplete data package; no files were changed.",
                missingFiles=[name for name, present in usable_cloud.items() if not present],
            )
        if all(usable_cloud.values()):
            # Setup is never a publish path.  A user may use this wizard to
            # point a new computer at an existing cloud package, but a
            # pre-existing different local package must be reconciled outside
            # the wizard rather than being copied over the cloud authority.
            local_paths = self._package_paths(local_dir)
            differing_local = [
                name
                for name in self._FILES
                if self._usable(local_paths[name])
                and self._sha256(local_paths[name]) != self._sha256(cloud_paths[name])
            ]
            if differing_local:
                return self._result(
                    False,
                    "conflict",
                    "Existing local and cloud packages differ; setup will not choose or overwrite either copy.",
                    files=differing_local,
                )
            return self._synchronize("setup")

        if seed_dir is None:
            return self._result(
                False,
                "seed-required",
                "Shared folder is empty. Select a one-time seed package to initialize it.",
            )
        seed_paths = self._package_paths(seed_dir)
        missing_seed = [name for name, path in seed_paths.items() if not self._usable(path)]
        if missing_seed:
            return self._result(
                False,
                "seed-invalid",
                "Seed folder does not contain a complete CSPM data package.",
                missingFiles=missing_seed,
            )

        try:
            for name in self._FILES:
                self._copy_verified(seed_paths[name], cloud_paths[name], "before_initial_cloud_seed")
            local_paths = self._package_paths(local_dir)
            for name in self._FILES:
                if not self._same_path(seed_paths[name], local_paths[name]):
                    self._copy_verified(seed_paths[name], local_paths[name], "before_initial_local_seed")
            state = self._get_state()
            self._set_base_hashes(state, {name: self._sha256(seed_paths[name]) for name in self._FILES})
            self._save_state(state)
            release = self._create_release(cloud_paths, "initial-seed")
            return self._result(
                True,
                "seeded",
                "Shared cloud authority and local replica were initialized from the one-time seed.",
                release=release,
            )
        except Exception as exc:
            logger.exception("SyncService initial setup failed")
            return self._result(False, "error", f"Initial cloud seeding failed: {exc}")

    def checkout_from_cloud(self) -> Dict[str, Any]:
        """Acquire exclusive writer ownership, then safely refresh local data."""
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            self._lease_owned = True
            return self._result(True, "local-only", "No shared cloud data folder is configured.")
        if self._same_path(master_dir, self.paths.data_dir()):
            self._lease_owned = False
            return self._result(
                False,
                "same-folder",
                "Shared and local folders must be different. CSPM opened read-only to protect the cloud package.",
            )

        lease_result = self._acquire_checkout_lease()
        if not lease_result.get("ok"):
            return lease_result
        sync_result = self._synchronize("checkout")
        if sync_result.get("ok"):
            sync_result["checkout"] = lease_result.get("lease", {})
            return sync_result

        # Never retain a writer lease for a conflict/error that left the
        # session read-only.  The untouched local candidate is still present.
        release_result = self._release_checkout_lease()
        sync_result["leaseRelease"] = release_result
        return sync_result

    def publish_and_release(self) -> Dict[str, Any]:
        """Publish a checked-out local package, then release the writer lease."""
        if self._shutdown_complete:
            return self._result(True, "already-released", "Shared checkout was already finalized for this session.")
        master_dir = self.paths.master_data_dir()
        if not master_dir:
            self._shutdown_complete = True
            self._lease_owned = False
            return self._result(True, "local-only", "No shared cloud folder is configured.")

        try:
            self.assert_write_lease()
            result = self._synchronize("publish", create_release=True)
        except PermissionError as exc:
            result = self._result(False, "not-checked-out", str(exc))
        finally:
            # The local package remains untouched if publishing failed.  Do not
            # strand the shared folder after a normal close; the failure result
            # tells the next launch that reconciliation is required.
            release_result = self._release_checkout_lease()
            self._shutdown_complete = True

        result["leaseRelease"] = release_result
        if not release_result.get("ok") and result.get("ok"):
            result["ok"] = False
            result["status"] = "release-error"
            result["message"] = release_result.get("message", "Could not release the shared checkout.")
        return result

    # Retain the controller's existing call surface.  A startup pull is now a
    # checkout; a shutdown push is now an archive-backed publish and release.
    def pull_from_master(self) -> Dict[str, Any]:
        return self.checkout_from_cloud()

    def push_to_master(self) -> Dict[str, Any]:
        return self.publish_and_release()
