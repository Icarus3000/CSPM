from __future__ import annotations

import io
import sys
import threading
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src" / "python"))

from services import holiday_calendar_service as module
from services.holiday_calendar_service import HolidayCalendarService, HolidayFeedError


def config(*enabled):
    return {"holidaySources": {source: source in enabled for source in ("CA", "US", "JEWISH")}}


def no_http(*args, **kwargs):
    pytest.fail("Country calendars must not make HTTP requests")


def test_disabled_sources_do_no_provider_or_network_work():
    service = HolidayCalendarService(transport=no_http, country_provider=no_http)
    result = service.fetch(config(), date(2026, 12, 28), date(2027, 1, 4))

    assert result["events"] == [] and result["errors"] == []
    assert [item["id"] for item in result["calendars"]] == [
        "holidays:CA", "holidays:US", "holidays:JEWISH",
    ]
    assert all(item["enabled"] is False for item in result["calendars"])


def test_disabled_calendar_ids_also_disable_supplemental_sources():
    configuration = config("CA", "US", "JEWISH")
    configuration["disabledCalendarIds"] = ["holidays:CA", "holidays:US", "holidays:JEWISH"]
    result = HolidayCalendarService(transport=no_http, country_provider=no_http).fetch(
        configuration, "2026-12-28", "2027-01-04",
    )
    assert result["events"] == [] and result["errors"] == []
    assert all(item["enabled"] is False for item in result["calendars"])


def test_country_configuration_is_ontario_national_us_and_observed(monkeypatch):
    calls = []

    def fake_country_holidays(country, **options):
        calls.append((country, options))
        return {date(2026, 7, 1): "Canada Day"} if country == "CA" else {
            date(2026, 7, 3): "Independence Day (observed)",
            date(2026, 7, 4): "Independence Day",
        }

    monkeypatch.setitem(sys.modules, "holidays", SimpleNamespace(country_holidays=fake_country_holidays))
    service = HolidayCalendarService(transport=no_http)
    result = service.fetch(config("CA", "US"), date(2026, 7, 1), date(2026, 7, 4))

    assert calls == [
        ("CA", {"subdiv": "ON", "years": [2026], "observed": True,
                "expand": False, "language": "en_CA"}),
        ("US", {"subdiv": None, "years": [2026], "observed": True,
                "expand": False, "language": "en_US"}),
    ]
    assert [(event["date"], event["title"]) for event in result["events"]] == [
        ("2026-07-01", "Canada Day"),
        ("2026-07-03", "Independence Day (observed)"),
        ("2026-07-04", "Independence Day"),
    ]
    assert all(event["publisherDate"] == event["date"] for event in result["events"])
    assert all("statutory" not in event for event in result["events"])


def test_actual_country_package_keeps_observed_days_and_region_scope():
    service = HolidayCalendarService(transport=no_http)
    independence = service.fetch(config("US"), "2026-07-03", "2026-07-04")
    assert [(event["date"], event["title"]) for event in independence["events"]] == [
        ("2026-07-03", "Independence Day (observed)"),
        ("2026-07-04", "Independence Day"),
    ]
    family_day = service.fetch(config("CA"), "2026-02-16", "2026-02-16")
    assert [event["title"] for event in family_day["events"]] == ["Family Day"]
    quebec = service.fetch(config("CA"), "2026-06-24", "2026-06-24")
    assert quebec["events"] == [] and quebec["errors"] == []
    state_only = service.fetch(config("US"), "2026-03-31", "2026-03-31")
    assert state_only["events"] == [] and state_only["errors"] == []
    new_year = service.fetch(config("US"), "2021-12-31", "2022-01-01")
    assert [(event["date"], event["title"]) for event in new_year["events"]] == [
        ("2021-12-31", "New Year's Day (observed)"),
        ("2022-01-01", "New Year's Day"),
    ]


def test_year_boundary_is_inclusive_without_duplicate_provider_items():
    calls = []

    def provider(country, year):
        calls.append((country, year))
        # Adjacent-year observed items may be emitted by both provider years.
        return {date(2026, 12, 31): "New Year's Day (observed)",
                date(2027, 1, 1): "New Year's Day",
                date(2027, 1, 7): "Outside range"}

    service = HolidayCalendarService(transport=no_http, country_provider=provider)
    result = service.fetch(config("US"), date(2026, 12, 31), date(2027, 1, 6))

    assert calls == [("US", 2026), ("US", 2027)]
    assert [event["date"] for event in result["events"]] == ["2026-12-31", "2027-01-01"]
    assert len({event["uid"] for event in result["events"]}) == 2
    assert result["events"][1]["end"] == "2027-01-02T00:00:00-05:00"


def test_toronto_all_day_boundaries_follow_dst_not_fixed_offset():
    service = HolidayCalendarService(transport=no_http, country_provider=lambda *_: {
        date(2026, 3, 8): "Spring boundary", date(2026, 11, 1): "Autumn boundary",
    })
    spring = service.fetch(config("CA"), "2026-03-08", "2026-03-08")["events"][0]
    autumn = service.fetch(config("CA"), "2026-11-01", "2026-11-01")["events"][0]

    assert spring["start"] == "2026-03-08T00:00:00-05:00"
    assert spring["end"] == "2026-03-09T00:00:00-04:00"
    assert autumn["start"] == "2026-11-01T00:00:00-04:00"
    assert autumn["end"] == "2026-11-02T00:00:00-05:00"
    assert all(event["allDay"] is True and event["isCurrent"] is False for event in (spring, autumn))


def test_hebcal_uses_public_diaspora_query_and_holidays_only():
    calls = []

    def transport(url, **options):
        calls.append((url, options))
        return {"items": [
            {"title": "Pesach I", "date": "2026-04-02", "category": "holiday",
             "subcat": "major", "link": "https://www.hebcal.com/holidays/pesach-2026"},
            {"title": "Pesach I", "date": "2026-04-02", "category": "holiday"},
            {"title": "Wrong source", "date": "2026-04-02", "category": "parashat"},
            {"title": "Daily Hebrew date", "date": "2026-04-02", "category": "hebdate"},
            {"title": "Shabbat HaGadol", "date": "2026-04-02", "category": "holiday", "subcat": "shabbat"},
            {"title": "Timed candle", "date": "2026-04-02T18:00:00-04:00", "category": "holiday"},
            {"title": "Later holiday", "date": "2026-04-03", "category": "holiday"},
        ]}

    result = HolidayCalendarService(transport=transport, country_provider=no_http).fetch(
        config("JEWISH"), date(2026, 4, 2), date(2026, 4, 2),
    )

    parsed = urlsplit(calls[0][0])
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https" and parsed.netloc == "www.hebcal.com"
    assert query["i"] == ["off"] and query["year"] == ["2026"]
    assert all(query[key] == ["on"] for key in ("maj", "min", "mf", "mod"))
    assert all(query[key] == ["off"] for key in ("nx", "ss", "s", "c", "d", "D"))
    assert not ({"email", "token", "zip", "geo", "latitude", "longitude"} & query.keys())
    assert 0 < calls[0][1]["timeout"] <= 15
    assert [event["title"] for event in result["events"]] == ["Pesach I"]
    assert result["events"][0]["sourceCalendars"] == ["Jewish holidays"]
    assert result["calendars"][2]["provider"] == "Hebcal.com"


def test_partial_source_failure_preserves_other_holidays_without_error_details():
    def countries(country, year):
        if country == "US":
            raise RuntimeError("sensitive token and response body must not be exposed")
        return {date(2026, 12, 25): "Christmas Day"}

    service = HolidayCalendarService(
        country_provider=countries,
        transport=lambda *args, **kwargs: {"items": [{
            "title": "Chanukah", "date": "2026-12-25", "category": "holiday",
            "link": "https://example.test/private?token=secret",
        }]},
    )
    result = service.fetch(config("CA", "US", "JEWISH"), "2026-12-25", "2026-12-25")

    assert {event["title"] for event in result["events"]} == {"Christmas Day", "Chanukah"}
    assert result["errors"] == ["US holidays could not be refreshed."]
    jewish = next(event for event in result["events"] if event["title"] == "Chanukah")
    assert jewish["webUrl"] == "https://www.hebcal.com/"


def test_cache_expires_and_does_not_share_mutable_display_events():
    now = [0.0]
    calls = []

    def provider(country, year):
        calls.append((country, year))
        return {date(2026, 7, 1): "Canada Day"}

    service = HolidayCalendarService(
        transport=no_http, country_provider=provider, clock=lambda: now[0],
    )
    first = service.fetch(config("CA"), "2026-07-01", "2026-07-01")
    first["events"][0]["title"] = "Changed outside service"
    first["events"][0]["sourceCalendars"].clear()
    now[0] = 299.0
    second = service.fetch(config("CA"), "2026-07-01", "2026-07-01")
    assert second["events"][0]["title"] == "Canada Day"
    assert second["events"][0]["sourceCalendars"] == ["Canadian holidays"]
    assert len(calls) == 1
    now[0] = 300.0
    service.fetch(config("CA"), "2026-07-01", "2026-07-01")
    assert len(calls) == 2


def test_failed_hebcal_response_is_not_cached():
    calls = []

    def transport(*args, **kwargs):
        calls.append(1)
        return {"wrong": []} if len(calls) == 1 else {"items": []}

    service = HolidayCalendarService(transport=transport, country_provider=no_http)
    first = service.fetch(config("JEWISH"), "2026-12-25", "2026-12-25")
    second = service.fetch(config("JEWISH"), "2026-12-25", "2026-12-25")
    assert first["errors"] == ["Jewish holidays could not be refreshed."]
    assert second["errors"] == [] and len(calls) == 2


def test_cancellation_stops_following_sources_and_withholds_partial_agenda():
    cancelled = threading.Event()
    calls = []

    def provider(country, year):
        calls.append(country)
        cancelled.set()
        return {date(2026, 7, 1): "Canada Day"}

    service = HolidayCalendarService(transport=no_http, country_provider=provider)
    result = service.fetch(config("CA", "US", "JEWISH"), "2026-07-01", "2026-07-01", cancelled)
    assert calls == ["CA"] and result["events"] == []
    assert result["errors"] == ["Holiday refresh cancelled."]
    result = service.fetch(config("CA", "US", "JEWISH"), "2026-07-01", "2026-07-01", cancelled)
    assert calls == ["CA"] and result["errors"] == ["Holiday refresh cancelled."]


@pytest.mark.parametrize("start,end", [("bad", "2026-01-01"), ("2026-02-30", "2026-03-01"),
                                          ("2026-01-02", "2026-01-01"), ("2026-01-01", "2028-01-01")])
def test_invalid_or_excessive_date_ranges_do_not_contact_sources(start, end):
    result = HolidayCalendarService(transport=no_http, country_provider=no_http).fetch(
        config("CA", "JEWISH"), start, end,
    )
    assert result["events"] == [] and result["errors"] == ["The holiday date range is invalid."]


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, body, url, headers=None):
        super().__init__(body)
        self.url = url
        self.headers = headers or {}

    def geturl(self):
        return self.url


def test_default_https_reader_rejects_redirects_and_unknown_origins():
    with pytest.raises(HolidayFeedError, match="redirect"):
        module._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test/")
    with pytest.raises(HolidayFeedError, match="Unsupported"):
        module._public_json("http://www.hebcal.com/hebcal", timeout=1)
    with pytest.raises(HolidayFeedError, match="Unsupported"):
        module._public_json("https://www.hebcal.com.evil.test/", timeout=1)


@pytest.mark.parametrize("declared", [False, True])
def test_default_reader_rejects_oversized_responses(monkeypatch, declared):
    url = "https://www.hebcal.com/hebcal"
    response = FakeResponse(
        b" " * (512 * 1024 + 1), url,
        {"Content-Length": str(512 * 1024 + 1)} if declared else {},
    )
    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=lambda *a, **kw: response))
    with pytest.raises(HolidayFeedError, match="too large"):
        module._public_json(url, timeout=1)


def test_default_reader_get_is_bounded_and_checks_cancellation(monkeypatch):
    url = "https://www.hebcal.com/hebcal"
    cancelled = threading.Event()
    received = []

    def open_response(request, *, timeout):
        received.append((request, timeout))
        cancelled.set()
        return FakeResponse(b'{"items": []}', url)

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=open_response))
    with pytest.raises(HolidayFeedError, match="cancelled"):
        module._public_json(url, timeout=1, cancel_event=cancelled)
    assert received[0][0].get_method() == "GET" and received[0][1] == 1
    assert "Authorization" not in received[0][0].headers
