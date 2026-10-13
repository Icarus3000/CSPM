"""Read-only public holiday supplements for the Microsoft 365 agenda.

Country dates are generated locally with python-holidays, including actual
and observed dates. Canada includes national and Ontario entries; the US
includes national entries only. These are calendar information, not legal
determinations of statutory days off. Hebcal uses its diaspora schedule
without daily learning, dates or Shabbat entries. Hebcal data is CC-BY-4.0:
the calendar descriptor carries provider attribution.

Provider documentation:
https://holidays.readthedocs.io/en/latest/api/
https://www.hebcal.com/home/195/jewish-calendar-rest-api
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import date, datetime, time as day_time, timedelta
from collections.abc import Mapping
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class HolidayFeedError(ValueError):
    """A public feed could not be safely read."""


class _Cancelled(HolidayFeedError):
    pass


def _check_cancel(cancel_event: Any) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise _Cancelled("Holiday refresh cancelled.")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HolidayFeedError("Holiday feed redirects are not permitted.")


def _public_json(url: str, *, timeout: float, cancel_event: Any = None) -> Any:
    """GET only a fixed provider origin; bound bytes, redirects and socket wait."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.hebcal.com"
        or parsed.username is not None
        or parsed.fragment
    ):
        raise HolidayFeedError("Unsupported holiday feed address.")
    _check_cancel(cancel_event)
    request = Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "CSPM-HolidayCalendar/1.0",
    }, method="GET")
    max_bytes = 512 * 1024
    deadline = time.monotonic() + timeout
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        if response.geturl() != url or response.status != 200:
            raise HolidayFeedError("Unexpected holiday feed response.")
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None and int(declared_length) > max_bytes:
            raise HolidayFeedError("Holiday feed response is too large.")
        chunks = []
        byte_count = 0
        while True:
            _check_cancel(cancel_event)
            if time.monotonic() >= deadline:
                raise HolidayFeedError("Holiday feed request timed out.")
            chunk = response.read(min(16384, max_bytes + 1 - byte_count))
            if not chunk:
                break
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise HolidayFeedError("Holiday feed response is too large.")
            chunks.append(chunk)
        _check_cancel(cancel_event)
    return json.loads(b"".join(chunks).decode("utf-8-sig"))


def _text(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", value).split())[:limit]


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _hebcal_link(value: Any) -> str:
    text = _text(value, 2048)
    try:
        parsed = urlsplit(text)
        if (
            parsed.scheme == "https"
            and parsed.netloc in {"hebcal.com", "www.hebcal.com"}
            and parsed.username is None
            and not parsed.fragment
        ):
            return text
    except ValueError:
        pass
    return "https://www.hebcal.com/"


class HolidayCalendarService:
    """Public annual JSON feeds; no account identifiers, tokens or persistence.

    Injected transport is callable(url, timeout=seconds, cancel_event=event)
    and returns a decoded Hebcal JSON object. An injected country provider is
    callable(country_code, year) and returns a date-to-name mapping. Only
    successful yearly results are cached, for five minutes by default;
    returned event objects are rebuilt.
    """

    SOURCES = (
        ("CA", "Canadian holidays", "python-holidays", "https://holidays.readthedocs.io/"),
        ("US", "US holidays", "python-holidays", "https://holidays.readthedocs.io/"),
        ("JEWISH", "Jewish holidays", "Hebcal.com", "https://www.hebcal.com/"),
    )

    def __init__(
        self,
        transport: Callable[..., Any] | None = None,
        *,
        country_provider: Callable[[str, int], Mapping] | None = None,
        timeout: float = 8.0,
        cache_ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._transport = transport or _public_json
        self._country_provider = country_provider or self._country_holidays
        self._timeout = max(0.1, min(float(timeout), 15.0))
        self._ttl = max(0.0, float(cache_ttl_seconds))
        self._clock = clock
        self._cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def _country_holidays(source: str, year: int) -> Mapping:
        # Lazy import keeps provider expansion out of application startup.
        from holidays import country_holidays

        return country_holidays(
            source, subdiv="ON" if source == "CA" else None,
            years=[year], observed=True, expand=False,
            language="en_CA" if source == "CA" else "en_US",
        )

    @staticmethod
    def _url(year: int) -> str:
        parameters = {
            "v": "1", "cfg": "json", "year": str(year), "yt": "G",
            "month": "x", "i": "off", "maj": "on", "min": "on",
            "mf": "on", "mod": "on", "nx": "off", "ss": "off",
            "s": "off", "c": "off", "d": "off", "D": "off",
            "o": "off", "leyning": "off",
        }
        return "https://www.hebcal.com/hebcal?" + urlencode(parameters)

    def _year_rows(self, source: str, year: int, cancel_event: Any) -> list[dict]:
        _check_cancel(cancel_event)
        key = (source, year)
        now = self._clock()
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self._ttl:
                return cached[1]
        if source == "JEWISH":
            payload = self._transport(
                self._url(year), timeout=self._timeout, cancel_event=cancel_event,
            )
            _check_cancel(cancel_event)
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise HolidayFeedError("Invalid Jewish holiday response.")
            rows = payload["items"]
        else:
            payload = self._country_provider(source, year)
            _check_cancel(cancel_event)
            if not isinstance(payload, Mapping) or len(payload) > 2000:
                raise HolidayFeedError("Invalid holiday response.")
            rows = [{"date": day, "name": name} for day, name in payload.items()]
        if len(rows) > 2000 or any(not isinstance(row, dict) for row in rows):
            raise HolidayFeedError("Invalid holiday response.")
        with self._cache_lock:
            self._cache[key] = (self._clock(), rows)
            # Public cache stays bounded if a user changes their system date.
            while len(self._cache) > 12:
                self._cache.pop(next(iter(self._cache)))
        return rows

    @staticmethod
    def _included(source: str, row: dict) -> bool:
        if source == "JEWISH":
            return row.get("category") == "holiday" and row.get("subcat") != "shabbat"
        return True

    def fetch(
        self, config: dict, start_date: date | str, end_date: date | str,
        cancel_event: Any = None,
    ) -> dict:
        sources = config.get("holidaySources", {}) if isinstance(config, dict) else {}
        if not isinstance(sources, dict):
            sources = {}
        raw_disabled = config.get("disabledCalendarIds", []) if isinstance(config, dict) else []
        disabled = set(item for item in raw_disabled if isinstance(item, str)) if isinstance(raw_disabled, list) else set()
        calendars = [{
            "id": "holidays:" + source, "name": name, "owner": "",
            "enabled": sources.get(source, True) is True and "holidays:" + source not in disabled,
            "source": source,
            "provider": provider, "attributionUrl": attribution,
        } for source, name, provider, attribution in self.SOURCES]
        result: dict = {"calendars": calendars, "events": [], "errors": []}
        start, end = _date(start_date), _date(end_date)
        if start is None or end is None or end == date.max or end < start or (end - start).days > 366:
            result["errors"].append("The holiday date range is invalid.")
            return result
        if not any(item["enabled"] for item in calendars):
            return result
        try:
            _check_cancel(cancel_event)
            toronto = ZoneInfo("America/Toronto")
        except _Cancelled:
            result["errors"].append("Holiday refresh cancelled.")
            return result
        except ZoneInfoNotFoundError:
            result["errors"].append("Toronto time zone data is unavailable.")
            return result
        seen = set()
        try:
            for calendar in calendars:
                if not calendar["enabled"]:
                    continue
                source = calendar["source"]
                for year in range(start.year, end.year + 1):
                    _check_cancel(cancel_event)
                    try:
                        rows = self._year_rows(source, year, cancel_event)
                    except _Cancelled:
                        raise
                    except Exception:
                        message = calendar["name"] + " could not be refreshed."
                        if message not in result["errors"]:
                            result["errors"].append(message)
                        continue
                    for row in rows:
                        _check_cancel(cancel_event)
                        if not self._included(source, row):
                            continue
                        event_date = _date(row.get("date"))
                        if event_date is None or not start <= event_date <= end:
                            continue
                        title = _text(row.get("title") if source == "JEWISH" else row.get("name"))
                        if not title:
                            continue
                        provider_id = _text(row.get("uid") or row.get("id"), 500) or title.casefold()
                        identity = (source, event_date.isoformat(), provider_id)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        digest = hashlib.sha256("\x00".join(identity).encode("utf-8")).hexdigest()[:24]
                        uid = "holidays:" + source + ":" + digest
                        result["events"].append({
                            "id": uid, "uid": uid, "title": title,
                            "start": datetime.combine(event_date, day_time.min, toronto).isoformat(),
                            "end": datetime.combine(event_date + timedelta(days=1), day_time.min, toronto).isoformat(),
                            "date": event_date.isoformat(), "allDay": True,
                            "sourceCalendars": [calendar["name"]], "location": "",
                            "webUrl": _hebcal_link(row.get("link")) if source == "JEWISH" else calendar["attributionUrl"],
                            "joinUrl": "", "isCurrent": False, "kind": "holiday",
                            "provider": calendar["provider"], "publisherDate": event_date.isoformat(),
                        })
                        # Preserve explicit provider metadata without inventing
                        # missing actual/observed dates or statutory designations.
                        for field in ("observedDate", "actualDate"):
                            published_date = _date(row.get(field))
                            if published_date is not None:
                                result["events"][-1][field] = published_date.isoformat()
        except _Cancelled:
            result["events"] = []
            result["errors"].append("Holiday refresh cancelled.")
        result["events"].sort(key=lambda item: (item["start"], item["title"].casefold(), item["id"]))
        return result
