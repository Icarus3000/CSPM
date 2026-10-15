"""Synthetic account replies and clocks only; no inference or network usage."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.usage_control.allowance import evaluate, normalize_response, read_live


NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)


def response(five_used=20, weekly_used=40):
    return {"rateLimits": {
        "limitId": "codex",
        "primary": {"usedPercent": five_used, "windowDurationMins": 300, "resetsAt": int((NOW + timedelta(hours=2)).timestamp())},
        "secondary": {"usedPercent": weekly_used, "windowDurationMins": 10080, "resetsAt": int((NOW + timedelta(days=3)).timestamp())},
    }}


def observation(five_used=20, weekly_used=40):
    return normalize_response(response(five_used, weekly_used), NOW)


class NormalizationTests(unittest.TestCase):
    def test_numeric_only_with_actual_durations_and_timezones(self):
        value = response()
        value["account"] = {"email": "secret@example.invalid", "accessToken": "secret"}
        value["rateLimits"]["credits"] = {"balance": "secret"}
        result = normalize_response(value, NOW)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["windows"]["five_hour"]["remaining_percent"], 80)
        self.assertEqual(result["windows"]["weekly"]["remaining_percent"], 60)
        self.assertTrue(result["observed_at_utc"].endswith("Z"))
        self.assertTrue(result["observed_at_toronto"].endswith("-04:00"))
        self.assertNotIn("secret", json.dumps(result))

    def test_prefer_explicit_codex_multi_bucket(self):
        value = response()
        value["rateLimitsByLimitId"] = {"codex": response(10, 15)["rateLimits"], "other": {"usedPercent": 100}}
        self.assertEqual(normalize_response(value, NOW)["windows"]["weekly"]["used_percent"], 15)

    def test_provider_equivalent_is_not_mislabeled(self):
        value = response()
        value["rateLimits"]["primary"]["windowDurationMins"] = 15
        result = normalize_response(value, NOW)
        self.assertEqual(result["diagnostic_code"], "unsupported_quota_windows")
        self.assertEqual(result["windows"], {})

    def test_window_order_does_not_define_its_label(self):
        value = response()
        bucket = value["rateLimits"]
        bucket["primary"], bucket["secondary"] = bucket["secondary"], bucket["primary"]
        self.assertEqual(normalize_response(value, NOW)["windows"]["five_hour"]["used_percent"], 20)

    def test_bad_percentages_are_rejected_without_clamping(self):
        for used in (-1, 101, True, None, "40", float("nan"), float("inf"), 10 ** 1000):
            with self.subTest(used=repr(used)[:30]):
                self.assertEqual(normalize_response(response(used), NOW)["status"], "unavailable")

    def test_missing_or_duplicate_window_is_unavailable(self):
        for mutation in ("missing", "duplicate"):
            value = response()
            if mutation == "missing":
                value["rateLimits"]["secondary"] = None
            else:
                value["rateLimits"]["secondary"]["windowDurationMins"] = 300
            self.assertEqual(normalize_response(value, NOW)["status"], "unavailable")

    def test_missing_reset_remains_unknown(self):
        value = response()
        del value["rateLimits"]["primary"]["resetsAt"]
        result = normalize_response(value, NOW)
        self.assertIsNone(result["windows"]["five_hour"]["reset_at_utc"])
        policy = evaluate(result, NOW)
        self.assertTrue(policy["work_allowed"])
        self.assertFalse(policy["resume_allowed"])
        self.assertIsNone(policy["resume_not_before_utc"])

    def test_invalid_reset_is_not_inferred(self):
        for reset in (-1, True, "2026-01-01", float("nan"), 10 ** 1000):
            value = response()
            value["rateLimits"]["primary"]["resetsAt"] = reset
            self.assertEqual(normalize_response(value, NOW)["status"], "unavailable")

    def test_missing_bucket_is_unavailable(self):
        for value in ({}, None, {"rateLimits": {"limitId": "other"}}):
            self.assertEqual(normalize_response(value, NOW)["status"], "unavailable")


class PolicyTests(unittest.TestCase):
    def test_normal_work_but_resume_requires_full_five_hour(self):
        result = evaluate(observation(), NOW)
        self.assertTrue(result["work_allowed"])
        self.assertFalse(result["resume_allowed"])
        self.assertFalse(result["checkpoint_required"])

    def test_exact_reserve_either_window(self):
        for used in ((85, 40), (20, 85), (100, 40), (20, 100)):
            result = evaluate(observation(*used), NOW)
            self.assertFalse(result["work_allowed"])
            self.assertTrue(result["checkpoint_required"])
            self.assertFalse(result["resume_allowed"])

    def test_next_batch_cannot_consume_reserve(self):
        result = evaluate(observation(70, 40), NOW, batch_budget_percent=15)
        self.assertFalse(result["work_allowed"])
        self.assertIn("five_hour_batch_would_use_reserve", result["work_reasons"])

    def test_unknown_batch_pauses_early_near_reserve(self):
        self.assertFalse(evaluate(observation(76, 40), NOW)["work_allowed"])
        self.assertTrue(evaluate(observation(75, 40), NOW)["work_allowed"])
        self.assertTrue(evaluate(observation(76, 40), NOW, batch_budget_percent=2)["work_allowed"])

    def test_freshness_boundary_and_future_timestamp(self):
        self.assertTrue(evaluate(observation(), NOW + timedelta(seconds=120))["work_allowed"])
        self.assertFalse(evaluate(observation(), NOW + timedelta(seconds=121))["work_allowed"])
        self.assertFalse(evaluate(observation(), NOW - timedelta(seconds=1))["work_allowed"])

    def test_cached_copy_keeps_original_observation_time(self):
        cached = json.loads(json.dumps(observation()))
        result = evaluate(cached, NOW + timedelta(days=1))
        self.assertFalse(result["fresh"])
        self.assertEqual(result["age_seconds"], 86400)
        self.assertIn("account_allowance_stale", result["work_reasons"])

    def test_unavailable_or_fabricated_allowance_fails_closed(self):
        for value in (None, {}, {"status": "unavailable"}, {"status": "ok"}):
            self.assertFalse(evaluate(value, NOW)["work_allowed"])
            self.assertFalse(evaluate(value, NOW)["resume_allowed"])

    def test_reset_gate_is_reported_plus_two_minutes(self):
        result = evaluate(observation(0, 40), NOW)
        self.assertTrue(result["resume_allowed"])
        self.assertTrue(result["resume_requires_recorded_gate"])
        self.assertEqual(result["resume_not_before_utc"], "2026-10-15T05:02:00Z")
        self.assertEqual(result["resume_not_before_toronto"], "2026-10-15T01:02:00-04:00")

    def test_weekly_reserve_blocks_full_primary_resume(self):
        self.assertFalse(evaluate(observation(0, 85), NOW)["resume_allowed"])
        self.assertTrue(evaluate(observation(0, 84), NOW, batch_budget_percent=0)["resume_allowed"])

    def test_context_capacity_is_independent(self):
        value = observation(0, 0)
        self.assertTrue(evaluate(value, NOW)["work_allowed"])
        result = evaluate(value, NOW, context_remaining_percent=15)
        self.assertFalse(result["work_allowed"])
        self.assertTrue(result["checkpoint_required"])
        self.assertEqual(value["windows"]["five_hour"]["remaining_percent"], 100)
        self.assertIn("context_checkpoint_required", result["work_reasons"])

    def test_reported_provider_block_is_honored(self):
        value = response(0, 0)
        value["rateLimits"]["rateLimitReachedType"] = "provider_defined_type"
        result = evaluate(normalize_response(value, NOW), NOW)
        self.assertFalse(result["work_allowed"])

    def test_invalid_policy_and_tampered_cache_fail_closed(self):
        for kwargs in ({"reserve_percent": True}, {"reserve_percent": 100}, {"max_age_seconds": -1}, {"batch_budget_percent": float("nan")}, {"context_remaining_percent": 101}):
            self.assertFalse(evaluate(observation(), NOW, **kwargs)["work_allowed"])
        value = observation()
        value["windows"]["weekly"]["remaining_percent"] = 99
        self.assertFalse(evaluate(value, NOW)["work_allowed"])


class ReaderTests(unittest.TestCase):
    def run_reader(self, body, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake_app_server.py"
            script.write_text(body, encoding="utf-8")
            return read_live([sys.executable, str(script)], NOW, timeout=timeout)

    def test_reader_sends_account_only_protocol(self):
        value = repr(response())
        body = f"""
import json,sys
a=json.loads(sys.stdin.readline())
assert a['method']=='initialize' and 'capabilities' not in a['params']
print(json.dumps({{'id':1,'result':{{}}}}),flush=True)
b=json.loads(sys.stdin.readline()); assert b['method']=='initialized'
c=json.loads(sys.stdin.readline()); assert c['method']=='account/rateLimits/read'
print(json.dumps({{'id':2,'result':{value}}}),flush=True)
assert not sys.stdin.readline()
"""
        self.assertEqual(self.run_reader(body)["status"], "ok")

    def test_buffered_multiple_json_lines_and_notifications(self):
        value = repr(response())
        body = f"""
import json,sys
sys.stdin.readline()
print(json.dumps({{'method':'notice','params':{{'accessToken':'private'}}}})+'\\n'+json.dumps({{'id':1,'result':{{}}}}),flush=True)
sys.stdin.readline();sys.stdin.readline()
print(json.dumps({{'method':'notice'}})+'\\n'+json.dumps({{'id':2,'result':{value}}}),flush=True)
"""
        result = self.run_reader(body)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("private", json.dumps(result))

    def test_unavailable_api_error_is_sanitized(self):
        result = self.run_reader("import sys,json\nsys.stdin.readline()\nprint(json.dumps({'id':1,'error':{'message':'SECRET_AUTH_TOKEN'}}),flush=True)\n")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_timeout_settles_reader(self):
        result = self.run_reader("import time\ntime.sleep(10)\n", timeout=0.05)
        self.assertEqual(result["diagnostic_code"], "account_read_timeout")

    def test_missing_executable_and_broken_json(self):
        self.assertEqual(read_live(["/missing/codex"], NOW)["status"], "unavailable")
        result = self.run_reader("import sys\nsys.stdin.readline()\nprint('invalid json',flush=True)\n")
        self.assertEqual(result["diagnostic_code"], "invalid_rpc_response")


if __name__ == "__main__":
    unittest.main()
