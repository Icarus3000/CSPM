from datetime import datetime
from pathlib import Path
import sys
import threading
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "python"))
from services.calendar_agenda_service import (
    CalendarAgendaService, CalendarFetchError, GraphTransport, _NoRedirect,
    empty_snapshot, sanitize_calendar_config,
)
from services.calendar_auth import CalendarAuthError


CONFIG = {"clientId": "d1234567-1234-1234-1234-123456789abc", "accountEmail": "lawyer@example.test", "holidaySources": {"CA": False, "US": False, "JEWISH": False}}


def calendar(identifier, name="Calendar"):
    return {"id": identifier, "name": name, "owner": {"address": CONFIG["accountEmail"]}}


def event(identifier, start, end, uid=None, **kwargs):
    return {
        "id": identifier, "iCalUId": uid or identifier, "subject": "Client meeting",
        "start": {"dateTime": start, "timeZone": "Eastern Standard Time"},
        "end": {"dateTime": end, "timeZone": "Eastern Standard Time"}, **kwargs,
    }


class Auth:
    def __init__(self):
        self.failure = None
        self.connect_count = 0
        self.disconnected = False

    def get_token(self, config, cancel_event=None):
        if self.failure:
            raise self.failure
        return {"access_token": "SECRET-TOKEN", "accountEmail": config["accountEmail"]}

    def connect(self, config, challenge_callback, cancel_event):
        self.connect_count += 1
        challenge_callback({"user_code": "ABCD", "verification_uri": "https://microsoft.com/devicelogin"})
        return self.get_token(config, cancel_event)

    def disconnect(self):
        self.disconnected = True


class Transport:
    def __init__(self, calendars, events=None):
        self.calendars = calendars
        self.events = events or {}
        self.calls = []
        self.extra_pages = {}

    def get_json(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        if url in self.extra_pages:
            result = self.extra_pages[url]
        elif urlsplit(url).path == "/v1.0/me/calendars":
            result = {"value": self.calendars}
        else:
            identifier = urlsplit(url).path.split("/")[-2]
            result = self.events.get(identifier, [])
            if isinstance(result, list):
                result = {"value": result}
        if isinstance(result, Exception):
            raise result
        return result


class Holidays:
    def __init__(self, values=None, errors=None):
        self.values = values or []
        self.errors = errors or []
        self.calls = []

    def fetch(self, config, start_date, end_date, cancel_event):
        self.calls.append((config, start_date, end_date))
        return {"calendars": [{"id": "holidays:CA", "name": "Canadian holidays", "source": "CA", "enabled": True, "owner": ""}], "events": self.values, "errors": self.errors}


def service(tmp_path, transport, *, clock="2026-10-13T12:00:00-04:00", auth=None, holidays=None):
    return CalendarAgendaService(tmp_path, holidays, now=lambda: datetime.fromisoformat(clock), auth=auth or Auth(), transport=transport)


def test_configuration_allows_only_nonsecret_fields_and_rejects_bad_identity_values():
    config = sanitize_calendar_config({**CONFIG, "timeZone": "Europe/London", "clientSecret": "MUST NOT SURVIVE", "access_token": "MUST NOT SURVIVE", "disabledCalendarIds": ["work", "work", 123], "holidaySources": {"CA": False}})
    assert set(config) == {"clientId", "tenantId", "accountEmail", "timeZone", "disabledCalendarIds", "holidaySources"}
    assert config["timeZone"] == "America/Toronto"
    assert config["disabledCalendarIds"] == ["work"]
    assert config["holidaySources"] == {"CA": False, "US": True, "JEWISH": True}
    assert sanitize_calendar_config({"clientId": "invalid", "tenantId": "../../attacker", "accountEmail": "bad"})["tenantId"] == "organizations"
    assert empty_snapshot({})["state"] == "unconfigured"
    assert empty_snapshot(CONFIG)["state"] == "disconnected"
    assert sanitize_calendar_config({**CONFIG, "tenantId": "tenant.example.test"})["tenantId"] == "tenant.example.test"


def test_today_excludes_finished_and_declined_cancelled_entries_keeps_current_and_future(tmp_path):
    transport = Transport([calendar("main")], {"main": [
        event("finished", "2026-10-13T09:00:00", "2026-10-13T10:00:00"),
        event("current", "2026-10-13T11:30:00", "2026-10-13T12:30:00"),
        event("upcoming", "2026-10-13T14:00:00", "2026-10-13T15:00:00"),
        event("cancelled", "2026-10-13T14:00:00", "2026-10-13T15:00:00", isCancelled=True),
        event("declined", "2026-10-13T14:00:00", "2026-10-13T15:00:00", responseStatus={"response": "declined"}),
        event("later", "2026-10-20T14:00:00", "2026-10-20T15:00:00"),
        event("too-late", "2026-10-21T00:00:00", "2026-10-21T01:00:00"),
    ]})
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert snapshot["state"] == "ready"
    assert [row["uid"] for row in snapshot["today"]] == ["current", "upcoming"]
    assert snapshot["today"][0]["isCurrent"] is True
    assert snapshot["today"][1]["isCurrent"] is False
    assert [row["uid"] for row in snapshot["next7Days"]] == ["later"]
    assert all(call[1]["Prefer"] == 'outlook.timezone="UTC"' and call[2] == 15 for call in transport.calls)
    assert "SECRET-TOKEN" not in str(snapshot)


@pytest.mark.parametrize("clock,start_offset,end_offset", [
    ("2026-03-07T12:00:00-05:00", "-05:00", "-04:00"),
    ("2026-10-31T12:00:00-04:00", "-04:00", "-05:00"),
])
def test_query_horizon_uses_toronto_midnights_with_dst_offsets(tmp_path, clock, start_offset, end_offset):
    transport = Transport([calendar("main")])
    snapshot = service(tmp_path, transport, clock=clock).fetch(CONFIG)
    assert snapshot["state"] == "ready"
    query = parse_qs(urlsplit(transport.calls[1][0]).query)
    start, end = query["startDateTime"][0], query["endDateTime"][0]
    assert start.endswith("T00:00:00" + start_offset)
    assert end.endswith("T00:00:00" + end_offset)
    assert (datetime.fromisoformat(end).date() - datetime.fromisoformat(start).date()).days == 8
    assert "/calendarView?" in transport.calls[1][0]


def test_fall_back_hour_keeps_separate_utc_occurrences_and_correct_toronto_offsets(tmp_path):
    first = event("first", "2026-11-01T05:15:00", "2026-11-01T05:45:00", uid="recurrence")
    second = event("second", "2026-11-01T06:15:00", "2026-11-01T06:45:00", uid="recurrence")
    for value in (first, second):
        value["start"]["timeZone"] = "UTC"
        value["end"]["timeZone"] = "UTC"
    transport = Transport([calendar("main")], {"main": [first, second]})
    snapshot = service(tmp_path, transport, clock="2026-11-01T04:30:00+00:00").fetch(CONFIG)
    assert [row["start"] for row in snapshot["today"]] == ["2026-11-01T01:15:00-04:00", "2026-11-01T01:15:00-05:00"]


def test_fall_back_meeting_spanning_repeated_hour_is_current_and_sorts_by_actual_instant(tmp_path):
    spanning = event("spanning", "2026-11-01T05:45:00", "2026-11-01T06:15:00")
    later = event("later", "2026-11-01T06:10:00", "2026-11-01T06:45:00")
    for value in (spanning, later):
        value["start"]["timeZone"] = value["end"]["timeZone"] = "UTC"
    transport = Transport([calendar("main")], {"main": [later, spanning]})
    snapshot = service(tmp_path, transport, clock="2026-11-01T06:05:00+00:00").fetch(CONFIG)
    assert [row["uid"] for row in snapshot["today"]] == ["spanning", "later"]
    assert snapshot["today"][0]["isCurrent"] is True
    assert snapshot["today"][0]["start"] == "2026-11-01T01:45:00-04:00"
    assert snapshot["today"][0]["end"] == "2026-11-01T01:15:00-05:00"


def test_enabled_owned_and_shared_custom_calendars_and_calendar_paging(tmp_path):
    second_page = "https://graph.microsoft.com/v1.0/me/calendars?$skiptoken=next"
    transport = Transport([calendar("main")], {"main": [], "shared": [], "disabled": [event("hidden", "2026-10-13T13:00:00", "2026-10-13T14:00:00")]})
    original = transport.get_json

    def get(url, headers, timeout):
        if urlsplit(url).path == "/v1.0/me/calendars" and url != second_page:
            transport.calls.append((url, headers, timeout))
            return {"value": [calendar("main")], "@odata.nextLink": second_page}
        return original(url, headers, timeout)

    transport.get_json = get
    transport.extra_pages[second_page] = {"value": [calendar("shared", "Shared custom"), calendar("disabled", "Hidden")]}
    snapshot = service(tmp_path, transport).fetch({**CONFIG, "disabledCalendarIds": ["disabled"]})
    assert [(row["id"], row["enabled"]) for row in snapshot["calendars"]] == [("main", True), ("shared", True), ("disabled", False)]
    assert any("/shared/calendarView?" in row[0] for row in transport.calls)
    assert not any("/disabled/calendarView?" in row[0] for row in transport.calls)


def test_deduplication_uses_uid_and_occurrence_start_preserves_distinct_same_title_meetings(tmp_path):
    first = event("one", "2026-10-13T14:00:00", "2026-10-13T15:00:00", uid="series-uid")
    duplicate = {**first, "id": "copy", "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/123"}}
    next_occurrence = event("next", "2026-10-14T14:00:00", "2026-10-14T15:00:00", uid="series-uid")
    distinct = event("different", "2026-10-13T14:00:00", "2026-10-13T15:00:00", uid="different-uid")
    transport = Transport([calendar("main", "Work"), calendar("shared", "Shared")], {"main": [first, next_occurrence, distinct], "shared": [duplicate]})
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert len(snapshot["today"]) == 2
    merged = next(row for row in snapshot["today"] if row["uid"] == "series-uid")
    assert merged["sourceCalendars"] == ["Work", "Shared"]
    assert merged["joinUrl"].startswith("https://teams.microsoft.com/")
    assert len(snapshot["next7Days"]) == 1


def test_all_day_cross_midnight_current_and_utc_conversion(tmp_path):
    transport = Transport([calendar("main")], {"main": [
        event("all-day", "2026-10-12T00:00:00", "2026-10-15T00:00:00", isAllDay=True),
        event("overnight", "2026-10-12T23:00:00", "2026-10-13T13:00:00"),
        event("utc", "2026-10-14T01:00:00Z", "2026-10-14T02:00:00Z"),
    ]})
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert [row["uid"] for row in snapshot["today"]] == ["all-day", "overnight", "utc"]
    assert all(row["date"] == "2026-10-13" for row in snapshot["today"])
    assert snapshot["today"][1]["isCurrent"] is True
    assert snapshot["today"][2]["start"] == "2026-10-13T21:00:00-04:00"
    assert snapshot["next7Days"][0]["uid"] == "all-day"
    assert snapshot["next7Days"][0]["date"] == "2026-10-14"


def test_known_holiday_sources_merge_exact_title_date_with_source_labels(tmp_path):
    holiday = {"id": "holidays:CA:one", "uid": "holiday-one", "title": "Thanksgiving", "start": "2026-10-13T00:00:00-04:00", "end": "2026-10-14T00:00:00-04:00", "date": "2026-10-13", "allDay": True, "sourceCalendars": ["Canadian holidays"], "location": "", "webUrl": "", "joinUrl": "", "isCurrent": False, "kind": "holiday"}
    graph_event = event("outlook-holiday", "2026-10-13T00:00:00", "2026-10-14T00:00:00", isAllDay=True, subject="Thanksgiving")
    # Same-title all-day appointment in an ordinary calendar remains distinct.
    transport = Transport([calendar("holiday", "Holidays in Canada"), calendar("work", "Work")], {"holiday": [graph_event], "work": [graph_event]})
    snapshot = service(tmp_path, transport, holidays=Holidays([holiday])).fetch(CONFIG)
    assert len(snapshot["today"]) == 2
    merged = next(row for row in snapshot["today"] if row["kind"] == "holiday")
    assert merged["sourceCalendars"] == ["Holidays in Canada", "Canadian holidays"]


@pytest.mark.parametrize("bad_url", ["https://steal.example.test/token", "http://graph.microsoft.com/v1.0/me/calendars", "https://graph.microsoft.com.evil.test/v1.0/me/calendars", "https://user:pass@graph.microsoft.com/v1.0/me/calendars", "https://graph.microsoft.com:444/v1.0/me/calendars"])
def test_paging_never_sends_bearer_token_to_untrusted_destination(tmp_path, bad_url):
    transport = Transport([calendar("main")], {"main": {"value": [event("valid", "2026-10-13T14:00:00", "2026-10-13T15:00:00")], "@odata.nextLink": bad_url}})
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert snapshot["state"] == "partial"
    assert len(snapshot["today"]) == 1
    assert not any(row[0] == bad_url for row in transport.calls)
    assert any("unexpected" in message for message in snapshot["errors"])
    assert "SECRET-TOKEN" not in str(snapshot)


def test_readable_page_survives_later_page_error_and_failures_are_explicit(tmp_path):
    next_page = "https://graph.microsoft.com/v1.0/me/calendars/main/calendarView?$skiptoken=next"
    transport = Transport([calendar("main"), calendar("unreadable", "Private shared")], {"main": {"value": [event("valid", "2026-10-13T14:00:00", "2026-10-13T15:00:00")], "@odata.nextLink": next_page}, "unreadable": CalendarFetchError("Microsoft denied access to this calendar.")})
    transport.extra_pages[next_page] = CalendarFetchError("Microsoft service is temporarily unavailable.")
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert snapshot["state"] == "partial"
    assert len(snapshot["today"]) == 1
    assert len(snapshot["errors"]) == 2
    assert "incomplete" in snapshot["message"]


def test_unreadable_event_and_unknown_timezone_do_not_make_successful_empty_agenda(tmp_path):
    raw = event("bad", "not-a-date", "2026-10-13T15:00:00")
    other = event("unknown-tz", "2026-10-13T14:00:00", "2026-10-13T15:00:00")
    other["start"]["timeZone"] = "Unknown/Untrusted"
    transport = Transport([calendar("main")], {"main": [raw, other]})
    snapshot = service(tmp_path, transport).fetch(CONFIG)
    assert snapshot["state"] == "partial"
    assert snapshot["today"] == [] and snapshot["errors"]


def test_previous_success_remains_explicitly_stale_after_total_fetch_failure_and_disconnect_clears(tmp_path):
    transport = Transport([calendar("main")], {"main": [event("valid", "2026-10-13T14:00:00", "2026-10-13T15:00:00")]})
    agenda = service(tmp_path, transport)
    first = agenda.fetch(CONFIG)
    transport.events["main"] = CalendarFetchError("Microsoft unavailable.")
    stale = agenda.fetch(CONFIG)
    assert stale["state"] == "error" and stale["stale"] is True
    assert stale["today"] == first["today"]
    assert stale["asOf"] == first["asOf"]
    agenda.disconnect()
    assert agenda._auth.disconnected
    assert agenda.fetch(CONFIG)["today"] == []
    assert agenda.fetch(CONFIG)["stale"] is False


def test_stale_account_agenda_never_survives_account_or_calendar_selection_change(tmp_path):
    transport = Transport([calendar("main")], {"main": [event("valid", "2026-10-13T14:00:00", "2026-10-13T15:00:00")]})
    agenda = service(tmp_path, transport)
    agenda.fetch(CONFIG)
    transport.events["main"] = CalendarFetchError("Unavailable.")
    assert agenda.fetch({**CONFIG, "accountEmail": "new-account@example.test"})["today"] == []
    assert agenda.fetch({**CONFIG, "disabledCalendarIds": ["main"]})["today"] == []


def test_failed_disconnect_still_forgets_in_memory_agenda_and_stale_fallback(tmp_path):
    transport = Transport([calendar("main")], {"main": [event("valid", "2026-10-13T14:00:00", "2026-10-13T15:00:00")]})
    auth = Auth()
    agenda = service(tmp_path, transport, auth=auth)
    agenda.fetch(CONFIG)

    def reject_disconnect():
        raise CalendarAuthError("The saved calendar sign-in could not be removed.")

    auth.disconnect = reject_disconnect
    with pytest.raises(CalendarAuthError):
        agenda.disconnect()
    assert agenda._last_snapshot is None and agenda._last_key is None


def test_unconfigured_and_disconnected_meetings_can_still_show_holiday_sources(tmp_path):
    transport = Transport([])
    auth = Auth()
    auth.failure = CalendarAuthError("Connect account.", "disconnected")
    holidays = Holidays(errors=["Jewish holidays could not be refreshed."])
    agenda = service(tmp_path, transport, auth=auth, holidays=holidays)
    snapshot = agenda.fetch(CONFIG)
    assert snapshot["state"] == "disconnected"
    assert snapshot["errors"] == holidays.errors
    assert snapshot["calendars"][0]["id"] == "holidays:CA"
    assert holidays.calls[0][1].isoformat() == "2026-10-13"
    assert holidays.calls[0][2].isoformat() == "2026-10-20"
    assert transport.calls == []
    assert agenda.fetch({})["state"] == "unconfigured"


def test_connect_delivers_challenge_then_fetches_and_cancelled_fetch_never_networks(tmp_path):
    transport = Transport([calendar("main")])
    auth = Auth()
    agenda = service(tmp_path, transport, auth=auth)
    challenges = []
    assert agenda.connect(CONFIG, challenges.append, threading.Event())["state"] == "ready"
    assert len(challenges) == 1 and auth.connect_count == 1
    transport.calls.clear()
    cancel = threading.Event()
    cancel.set()
    snapshot = agenda.fetch(CONFIG, cancel)
    assert snapshot["state"] == "error" and "cancelled" in snapshot["message"]
    assert transport.calls == []


def test_https_transport_blocks_redirects_and_redacts_raw_transport_exceptions(monkeypatch):
    assert _NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://attacker.example.test") is None
    with pytest.raises(CalendarFetchError, match="unexpected"):
        GraphTransport().get_json("https://attacker.example.test", {"Authorization": "Bearer secret"})


def test_http_errors_do_not_expose_response_body_or_sensitive_url(monkeypatch):
    from urllib.error import HTTPError

    class Opener:
        def open(self, request, timeout):
            raise HTTPError("https://graph.microsoft.com/v1.0/private-secret", 403, "RAW RESPONSE SECRET", {}, None)

    monkeypatch.setattr("services.calendar_agenda_service.build_opener", lambda *args: Opener())
    with pytest.raises(CalendarFetchError, match="denied access") as failure:
        GraphTransport().get_json("https://graph.microsoft.com/v1.0/me/calendars", {"Authorization": "Bearer secret"})
    assert "RAW RESPONSE" not in str(failure.value) and "private-secret" not in str(failure.value)
