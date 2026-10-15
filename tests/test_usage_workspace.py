"""Model-free workspace recovery tests with synthetic quotas and clocks."""

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.usage_control.allowance import evaluate, normalize_response, unavailable
from scripts.usage_control import workspace


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    _spec = importlib.util.spec_from_file_location("workspace_usage_under_test", SCRIPTS / "workspace_usage.py")
    cli = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(cli)
finally:
    sys.path.pop(0)

NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
RESET = NOW + timedelta(minutes=10)
GATE = RESET + timedelta(seconds=120)


def config():
    return {
        "enabled": True,
        "reserve_percent": 15,
        "max_observation_age_seconds": 120,
        "context_reserve_percent": 15,
        "reset_buffer_seconds": 120,
        "poll_seconds": 300,
        "retry_initial_seconds": 30,
        "retry_max_seconds": 120,
        "max_resume_checks": 3,
        "state_directory": ".workspace-usage",
        "account_command": ["/unexecuted/test/codex", "app-server"],
        "account_timeout_seconds": 1,
        "client": "synthetic-ide-private-app-server",
        "automatic_resume_supported": False,
        "automatic_resume_enabled": False,
        "limitation": "Synthetic fixture: no external resume interface",
    }


def quotas(now=NOW, five=85, weekly=20, reset=RESET, weekly_reset=None):
    if weekly_reset is None:
        weekly_reset = now + timedelta(days=3)
    return normalize_response({"rateLimits": {
        "limitId": "codex",
        "primary": {"usedPercent": five, "windowDurationMins": 300,
                    "resetsAt": reset.timestamp() if reset else None},
        "secondary": {"usedPercent": weekly, "windowDurationMins": 10080,
                      "resetsAt": weekly_reset.timestamp()},
    }}, now)


def checkpoint(checkpoint_id="pause-1", gate=GATE):
    return {"checkpoint_id": checkpoint_id, "resume_required": True,
            "earliest_resume_utc": gate.isoformat() if gate else None}


def notes():
    return {
        "objective": "Compile requested repository while preserving current work",
        "constraints": ["No second CLI owner", "No production data writes", "15% allowance reserve"],
        "completed": ["Synthetic implementation checkpoint"],
        "validation": ["Synthetic checks only; no WebEngine instantiated"],
        "unresolved": ["IDE resumption unsupported"],
        "active_tools": [{"session": "settled", "pid": None}],
        "child_agents": [{"state": "settled"}],
        "next_steps": [{"command": "python3 scripts/workspace_usage.py check", "purpose": "Fresh allowance gate"}],
    }


class GateAndRecoveryTests(unittest.TestCase):
    def ready(self, now=GATE, weekly=20):
        value = quotas(now, five=0, weekly=weekly, reset=now + timedelta(hours=5))
        return value, evaluate(value, now)

    def test_pause_snapshot_reset_plus_120_not_next_window_reset(self):
        for delta, expected in ((-1, False), (0, True), (1, True)):
            now = GATE + timedelta(seconds=delta)
            value, policy = self.ready(now)
            self.assertGreater(workspace.parse_time(policy["resume_not_before_utc"]), now)
            result = workspace.resume_gate(checkpoint(), value, policy, now, "verified_idle", config())
            self.assertEqual(result["prerequisites_met"], expected)
            self.assertFalse(result["automatic_resume_executed"])
            if not expected:
                self.assertIn("before_recorded_reset_plus_buffer", result["reasons"])

    def test_primary_must_be_fully_restored(self):
        value = quotas(GATE, five=1, reset=GATE + timedelta(hours=5))
        result = workspace.resume_gate(checkpoint(), value, evaluate(value, GATE), GATE, "verified_idle", config())
        self.assertFalse(result["prerequisites_met"])
        self.assertIn("five_hour_not_fully_restored", result["reasons"])

    def test_weekly_exhaustion_waits_for_actual_weekly_reset_plus_buffer(self):
        weekly_reset = GATE + timedelta(days=2)
        value = quotas(GATE, five=0, weekly=85, reset=GATE + timedelta(hours=5), weekly_reset=weekly_reset)
        result = workspace.next_check({}, checkpoint(), value, evaluate(value, GATE), GATE, config(), "verified_idle")
        self.assertEqual(result["phase"], "deferred")
        self.assertIn("weekly_reserve_reached", result["eligibility"]["reasons"])
        self.assertEqual(workspace.parse_time(result["next_check_utc"]), weekly_reset + timedelta(seconds=120))

    def test_stale_and_unavailable_allowance_cannot_authorize_resume(self):
        stale = quotas(NOW, five=0)
        for value in (stale, unavailable(GATE, "synthetic_api_unavailable")):
            result = workspace.resume_gate(checkpoint(), value, evaluate(value, GATE), GATE, "verified_idle", config())
            self.assertFalse(result["prerequisites_met"])
            self.assertFalse(result["automatic_resume_executed"])

    def test_active_unknown_and_missing_ownership_fail_closed(self):
        value, policy = self.ready()
        for ownership, reason in (("active", "active_owner"), ("unknown", "ownership_unverified"), (None, "ownership_unverified")):
            result = workspace.resume_gate(checkpoint(), value, policy, GATE, ownership, config())
            self.assertFalse(result["prerequisites_met"])
            self.assertIn(reason, result["reasons"])

    def test_no_resume_executor_even_if_capability_flags_are_changed(self):
        value, policy = self.ready()
        settings = config()
        settings.update(automatic_resume_supported=True, automatic_resume_enabled=True)
        with patch.object(workspace.subprocess, "run", side_effect=AssertionError("must not spawn")), patch.object(workspace.subprocess, "Popen", side_effect=AssertionError("must not spawn")):
            result = workspace.resume_gate(checkpoint(), value, policy, GATE, "verified_idle", settings)
            state = workspace.next_check({}, checkpoint(), value, policy, GATE, settings, "verified_idle")
        self.assertTrue(result["prerequisites_met"])
        self.assertEqual(result["action"], "manual_resume_ready")
        self.assertFalse(result["automatic_resume_executed"])
        self.assertFalse(state["eligibility"]["automatic_resume_executed"])

    def test_unknown_reset_cannot_be_reconstructed_from_new_observation(self):
        value, policy = self.ready()
        result = workspace.resume_gate(checkpoint(gate=None), value, policy, GATE, "verified_idle", config())
        self.assertFalse(result["prerequisites_met"])
        self.assertIn("pause_reset_unknown", result["reasons"])

    def test_before_gate_consumes_no_retry_or_ownership_attempt(self):
        value, policy = self.ready(GATE - timedelta(seconds=1))
        state = workspace.next_check({}, checkpoint(), value, policy, GATE - timedelta(seconds=1), config(), "active")
        self.assertEqual(state["phase"], "waiting_for_reset")
        self.assertEqual(state["attempts"], 0)
        self.assertEqual(workspace.parse_time(state["next_check_utc"]), GATE)

    def test_duplicate_trigger_and_restart_keep_backoff(self):
        value, policy = self.ready()
        state = workspace.next_check({}, checkpoint(), value, policy, GATE, config())
        self.assertEqual(state["attempts"], 1)
        # A real persisted JSON roundtrip represents an external scheduler restart.
        recovered = json.loads(json.dumps(state))
        duplicate = workspace.next_check(recovered, checkpoint(), value, policy, GATE, config())
        self.assertEqual(duplicate, state)
        next_time = workspace.parse_time(state["next_check_utc"])
        value, policy = self.ready(next_time)
        second = workspace.next_check(recovered, checkpoint(), value, policy, next_time, config())
        self.assertEqual(second["attempts"], 2)
        self.assertEqual(workspace.parse_time(second["next_check_utc"]), next_time + timedelta(seconds=60))

    def test_retry_exhaustion_is_durable_and_new_checkpoint_rearms(self):
        state = {}
        now = GATE
        for _ in range(config()["max_resume_checks"]):
            value, policy = self.ready(now)
            state = workspace.next_check(state, checkpoint(), value, policy, now, config())
            if state.get("next_check_utc"):
                now = workspace.parse_time(state["next_check_utc"])
        self.assertEqual(state["phase"], "retry_exhausted")
        recovered = json.loads(json.dumps(state))
        value, policy = self.ready(now + timedelta(days=1))
        self.assertEqual(workspace.next_check(recovered, checkpoint(), value, policy, now + timedelta(days=1), config()), recovered)
        renewed = workspace.next_check(recovered, checkpoint("pause-2"), value, policy, now + timedelta(days=1), config())
        self.assertEqual(renewed["attempts"], 1)
        self.assertEqual(renewed["checkpoint_id"], "pause-2")


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / ".workspace-usage"
        self.git("init", "--initial-branch=main")
        self.git("config", "user.email", "usage-test@example.invalid")
        self.git("config", "user.name", "Synthetic Usage Guard Test")
        (self.root / ".gitignore").write_text(".workspace-usage/\n")
        (self.root / "tracked name.txt").write_text("original\n")
        (self.root / "dirty.txt").write_text("before\n")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic fixture")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


class WorkspacePersistenceTests(GitFixture):
    def test_inventory_records_rename_dirty_and_newline_filename_without_changing_work(self):
        self.git("mv", "tracked name.txt", "renamed file.txt")
        (self.root / "dirty.txt").write_bytes(b"uncommitted\n")
        untracked = self.root / "untracked\nname.txt"
        untracked.write_bytes(b"preserve me\n")
        before = self.git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        result = workspace.git_inventory(self.root)
        by_name = {item["path"]: item for item in result["changes"]}
        self.assertEqual(result["branch"], "main")
        self.assertEqual(result["head"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertEqual(by_name["renamed file.txt"]["previous_path"], "tracked name.txt")
        self.assertEqual(by_name["dirty.txt"]["status"], " M")
        self.assertEqual(by_name[untracked.name]["status"], "??")
        self.assertEqual(len(by_name["dirty.txt"]["sha256"]), 64)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z", "--untracked-files=all"), before)
        self.assertEqual(untracked.read_bytes(), b"preserve me\n")
        self.assertEqual((self.root / "dirty.txt").read_bytes(), b"uncommitted\n")

    def test_sensitive_and_symlink_contents_are_not_hashed(self):
        (self.root / "auth.json").write_text("PRIVATE_CREDENTIAL_VALUE")
        (self.root / ".env").write_text("PRIVATE_AUTH_VALUE")
        (self.root / ".env.production").write_text("PRIVATE_PRODUCTION_AUTH")
        (self.root / "linked.txt").symlink_to(self.root / "auth.json")
        result = workspace.git_inventory(self.root)
        for item in result["changes"]:
            self.assertNotIn("sha256", item)
            self.assertFalse(item["content_recorded"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_unavailable_git_is_marked_unknown_without_invented_filename(self):
        with patch.object(workspace, "_git", return_value="unavailable"):
            result = workspace.git_inventory(self.root)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["changes"])

    def test_lock_excludes_another_process_and_recovers_after_holder_exit(self):
        child = """
import os,sys
from pathlib import Path
from scripts.usage_control.workspace import state_lock
try:
    with state_lock(Path(sys.argv[1])):
        os._exit(0)
except RuntimeError:
    sys.exit(75)
"""
        command = [sys.executable, "-c", child, str(self.state)]
        repo = Path(__file__).resolve().parents[1]
        with workspace.state_lock(self.state):
            result = subprocess.run(command, cwd=repo, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 75)
        result = subprocess.run(command, cwd=repo, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        with workspace.state_lock(self.state):
            pass

    def test_atomic_write_is_private_and_invalid_serialization_preserves_old_state(self):
        path = self.state / "state.json"
        workspace.atomic_json(path, {"generation": 1})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        with self.assertRaises(ValueError):
            workspace.atomic_json(path, {"generation": float("nan")})
        self.assertEqual(workspace.read_json(path), {"generation": 1})
        self.assertEqual(list(path.parent.glob(".pending-*")), [])

    def test_atomic_replace_failure_preserves_previous_complete_generation(self):
        path = self.state / "state.json"
        workspace.atomic_json(path, {"generation": 1})
        with patch.object(workspace.os, "replace", side_effect=OSError("simulated interrupted replace")):
            with self.assertRaises(OSError):
                workspace.atomic_json(path, {"generation": 2})
        self.assertEqual(workspace.read_json(path), {"generation": 1})
        self.assertEqual(list(path.parent.glob(".pending-*")), [])

    def test_lock_blocks_duplicate_and_releases_after_exception(self):
        with self.assertRaisesRegex(ValueError, "simulated crash"):
            with workspace.state_lock(self.state):
                with self.assertRaisesRegex(RuntimeError, "another_monitor_owns_state"):
                    with workspace.state_lock(self.state):
                        self.fail("second monitor acquired active lock")
                raise ValueError("simulated crash")
        with workspace.state_lock(self.state):
            pass

    def test_checkpoint_retains_objective_constraints_work_inventory_and_exact_gate(self):
        (self.root / "dirty.txt").write_text("current work\n")
        value = quotas()
        result = workspace.make_checkpoint(self.root, self.state, notes(), value, evaluate(value, NOW), NOW, config())
        self.assertEqual(result["objective"], notes()["objective"])
        self.assertEqual(result["constraints"], notes()["constraints"])
        self.assertEqual(result["active_tools"], notes()["active_tools"])
        self.assertEqual(result["earliest_resume_utc"], "2026-10-15T03:12:00Z")
        self.assertEqual(result["earliest_resume_toronto"], "2026-10-14T23:12:00-04:00")
        self.assertEqual(workspace.read_json(self.state / "latest-checkpoint.json"), result)
        self.assertEqual(workspace.read_json(self.state / "checkpoints" / (result["checkpoint_id"] + ".json")), result)
        self.assertEqual(workspace.read_json(self.state / "schedule.json")["attempts"], 0)
        self.assertEqual((self.root / "dirty.txt").read_text(), "current work\n")

    def test_new_checkpoint_resets_exhausted_schedule_and_keeps_previous_snapshot(self):
        value = quotas()
        first = workspace.make_checkpoint(self.root, self.state, notes(), value, evaluate(value, NOW), NOW, config())
        workspace.atomic_json(self.state / "schedule.json", {"checkpoint_id": first["checkpoint_id"], "phase": "retry_exhausted", "attempts": 3})
        now = NOW + timedelta(seconds=1)
        second = workspace.make_checkpoint(self.root, self.state, notes(), value, evaluate(value, now), now, config())
        self.assertNotEqual(first["checkpoint_id"], second["checkpoint_id"])
        self.assertEqual(workspace.read_json(self.state / "schedule.json")["attempts"], 0)
        self.assertTrue((self.state / "checkpoints" / (first["checkpoint_id"] + ".json")).exists())

    def test_missing_required_task_notes_cannot_create_incomplete_checkpoint(self):
        incomplete = notes()
        del incomplete["active_tools"]
        value = quotas()
        with self.assertRaises(ValueError):
            workspace.make_checkpoint(self.root, self.state, incomplete, value, evaluate(value, NOW), NOW, config())
        self.assertFalse((self.state / "latest-checkpoint.json").exists())

    def test_notes_cannot_override_checkpoint_identity_or_other_reserved_fields(self):
        value = quotas()
        for key, content in (("checkpoint_id", "other-checkpoint"), ("workspace", "/other/workspace"), ("earliest_resume_utc", None)):
            supplied = {**notes(), key: content}
            with self.assertRaises(ValueError):
                workspace.make_checkpoint(self.root, self.state, supplied, value, evaluate(value, NOW), NOW, config())
        self.assertFalse((self.state / "latest-checkpoint.json").exists())


class CliIntegrationTests(GitFixture):
    def setUp(self):
        super().setUp()
        (self.root / "usage-control.json").write_text(json.dumps(config()))

    def args(self, command="check"):
        return SimpleNamespace(root=self.root, command=command, notes=None, pause=False,
                               batch_budget_percent=None, context_remaining_percent=None)

    def invoke(self, observation, now=NOW, command="check"):
        output = io.StringIO()
        with patch.object(cli, "get_observation", return_value=observation) as reader, patch.object(cli, "datetime") as clock, redirect_stdout(output):
            clock.now.return_value = now
            code = cli.run_once(self.args(command))
        return code, json.loads(output.getvalue()), reader

    def test_check_live_gate_cached_fallback_is_timestamped_and_cannot_authorize(self):
        code, result, _ = self.invoke(quotas(five=20))
        self.assertEqual(code, 0)
        later = NOW + timedelta(minutes=5)
        code, result, _ = self.invoke(unavailable(later, "synthetic_api_unavailable"), later)
        self.assertEqual(code, 75)
        self.assertFalse(result["policy"]["work_allowed"])
        self.assertEqual(result["cached_age_seconds"], 300)
        self.assertEqual(result["cached_observation"]["observed_at_utc"], "2026-10-15T03:00:00Z")
        self.assertIn("cannot authorize", result["cached_warning"])

    def test_monitor_recovery_labels_unknown_live_tools_and_never_resumes_ide(self):
        workspace.atomic_json(self.state / "task-notes.json", notes())
        code, result, _ = self.invoke(quotas(), command="watch-once")
        self.assertEqual(code, 0)
        saved = workspace.read_json(self.state / "latest-checkpoint.json")
        self.assertTrue(saved["resume_required"])
        self.assertEqual(saved["checkpoint_kind"], "monitor_recovery_requires_agent_settlement")
        self.assertFalse(workspace.read_json(self.state / "pause-request.json")["automatic_interrupt_supported"])
        later = GATE + timedelta(seconds=1)
        code, result, _ = self.invoke(quotas(later, five=0, reset=later + timedelta(hours=5)), later, "watch-once")
        self.assertEqual(result["schedule"]["phase"], "deferred")
        self.assertIn("ownership_unverified", result["schedule"]["eligibility"]["reasons"])
        self.assertFalse(result["schedule"]["eligibility"]["automatic_resume_executed"])
        self.assertEqual(workspace.read_json(self.state / "latest-checkpoint.json")["earliest_resume_utc"], saved["earliest_resume_utc"])

    def test_no_live_rpc_before_due_or_after_retry_exhaustion(self):
        for state in ({"phase": "waiting", "next_check_utc": GATE.isoformat()}, {"phase": "retry_exhausted", "attempts": 3}):
            workspace.atomic_json(self.state / "schedule.json", state)
            code, result, reader = self.invoke(quotas(), command="watch-once")
            self.assertEqual(code, 0)
            reader.assert_not_called()

    def test_active_lock_prevents_duplicate_cli_reader(self):
        with cli.state_lock(self.state), patch.object(cli, "get_observation", side_effect=AssertionError("reader must not run")):
            with self.assertRaisesRegex(RuntimeError, "another_monitor_owns_state"):
                cli.run_once(self.args("watch-once"))

    def test_status_labels_saved_data_age_without_live_rpc(self):
        workspace.atomic_json(self.state / "observation.json", quotas())
        code, result, reader = self.invoke(quotas(), NOW + timedelta(minutes=5), "status")
        self.assertEqual(code, 0)
        self.assertTrue(result["saved_data_only"])
        self.assertEqual(result["observation_age_seconds"], 300)
        reader.assert_not_called()

    def test_restart_recovers_latest_checkpoint_when_schedule_write_was_interrupted(self):
        workspace.atomic_json(self.state / "latest-checkpoint.json", checkpoint("new-pause"))
        workspace.atomic_json(self.state / "schedule.json", {
            "checkpoint_id": "old-pause", "phase": "retry_exhausted", "attempts": 3,
            "next_check_utc": None,
        })
        later = GATE + timedelta(seconds=1)
        code, result, reader = self.invoke(quotas(later, five=0, reset=later + timedelta(hours=5)), later, "watch-once")
        self.assertEqual(code, 0)
        reader.assert_called_once()
        self.assertEqual(result["schedule"]["checkpoint_id"], "new-pause")
        self.assertEqual(result["schedule"]["attempts"], 1)
        self.assertEqual(result["schedule"]["phase"], "deferred")

    def test_config_cannot_enable_resume_or_escape_workspace(self):
        for key in ("automatic_resume_supported", "automatic_resume_enabled"):
            settings = config()
            settings[key] = True
            (self.root / "usage-control.json").write_text(json.dumps(settings))
            with self.assertRaises(ValueError):
                cli.load_config(self.root)
        settings = config()
        settings["state_directory"] = "../outside-workspace"
        (self.root / "usage-control.json").write_text(json.dumps(settings))
        with self.assertRaises(ValueError):
            cli.load_config(self.root)

    def test_monitor_install_is_idempotent_and_only_schedules_account_checks(self):
        units = self.root / "synthetic-units"
        service, timer = units / "cspm-usage-monitor.service", units / "cspm-usage-monitor.timer"
        with patch.object(cli, "unit_paths", return_value=(service, timer)), patch.object(cli.subprocess, "run") as runner, redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install_monitor(self.root), 0)
            first = service.read_bytes(), timer.read_bytes()
            self.assertEqual(cli.install_monitor(self.root), 0)
            self.assertEqual((service.read_bytes(), timer.read_bytes()), first)
        self.assertEqual(len(list(units.iterdir())), 2)
        self.assertIn("watch-once", service.read_text())
        self.assertNotIn("thread/resume", service.read_text())
        self.assertNotIn("turn/start", service.read_text())
        self.assertIn("OnUnitInactiveSec=300s", timer.read_text())
        self.assertTrue(all(call.args[0][:2] == ["systemctl", "--user"] for call in runner.call_args_list))

    def test_differing_scheduler_unit_is_preserved_without_starting_service(self):
        units = self.root / "synthetic-units"
        units.mkdir()
        service, timer = units / "cspm-usage-monitor.service", units / "cspm-usage-monitor.timer"
        service.write_text("existing unrelated local customization\n")
        with patch.object(cli, "unit_paths", return_value=(service, timer)), patch.object(cli.subprocess, "run") as runner:
            with self.assertRaises(ValueError):
                cli.install_monitor(self.root)
            runner.assert_not_called()
        self.assertEqual(service.read_text(), "existing unrelated local customization\n")
        self.assertFalse(timer.exists())

    def test_monitor_disable_and_remove_preserve_private_checkpoint(self):
        units = self.root / "synthetic-units"
        service, timer = units / "cspm-usage-monitor.service", units / "cspm-usage-monitor.timer"
        workspace.atomic_json(self.state / "latest-checkpoint.json", checkpoint())
        with patch.object(cli, "unit_paths", return_value=(service, timer)), patch.object(cli.subprocess, "run"), redirect_stdout(io.StringIO()):
            cli.install_monitor(self.root)
            cli.remove_monitor(False)
            self.assertTrue(service.exists())
            self.assertTrue(timer.exists())
            cli.remove_monitor(True)
        self.assertFalse(service.exists())
        self.assertFalse(timer.exists())
        self.assertEqual(workspace.read_json(self.state / "latest-checkpoint.json"), checkpoint())


if __name__ == "__main__":
    unittest.main()
