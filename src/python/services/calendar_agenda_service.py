"""Transport-neutral, read-only agenda for Microsoft 365 and holiday sources."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
import threading
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .calendar_auth import CalendarAuth, CalendarAuthError, CalendarCancelled, check_cancelled


TIME_ZONE = "America/Toronto"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# UTC response values preserve the repeated fall-back hour unambiguously.
# Request bounds still carry Toronto offsets; display conversion is local.
_GRAPH_PREFER = 'outlook.timezone="UTC"'
_MAX_PAGES = 200
_KNOWN_HOLIDAY_NAMES = {
    "canadian holidays", "canada holidays", "holidays in canada",
    "us holidays", "u.s. holidays", "united states holidays", "holidays in united states",
    "jewish holidays", "jewish religious holidays",
}


def _text(value, limit=1000) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _uuid(value) -> str:
    try:
        return str(UUID(_text(value)))
    except (ValueError, TypeError, AttributeError):
        return ""


def sanitize_calendar_config(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    tenant = _text(raw.get("tenantId"), 253) or "organizations"
    if tenant != "organizations" and not _uuid(tenant) and not re.fullmatch(
        r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", tenant
    ):
        tenant = "organizations"
    email = _text(raw.get("accountEmail"), 254)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        email = ""
    disabled = raw.get("disabledCalendarIds", [])
    disabled = list(dict.fromkeys(_text(v, 1024) for v in disabled if _text(v, 1024))) if isinstance(disabled, list) else []
    holiday_raw = raw.get("holidaySources", {})
    holiday_raw = holiday_raw if isinstance(holiday_raw, dict) else {}
    return {
        "clientId": _uuid(raw.get("clientId")), "tenantId": tenant,
        "accountEmail": email, "timeZone": TIME_ZONE,
        "disabledCalendarIds": disabled,
        "holidaySources": {key: holiday_raw.get(key, True) is not False for key in ("CA", "US", "JEWISH")},
    }


def empty_snapshot(config) -> dict:
    config = sanitize_calendar_config(config)
    configured = bool(config["clientId"] and config["accountEmail"])
    return {
        "state": "disconnected" if configured else "unconfigured",
        "message": "Connect your Microsoft 365 account to load meetings." if configured else
                   "Add your Microsoft application ID and calendar account, then connect to load meetings.",
        "accountEmail": config["accountEmail"], "asOf": "", "timeZone": TIME_ZONE,
        "calendars": [], "today": [], "next7Days": [], "stale": False, "errors": [],
    }


class CalendarFetchError(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an Authorization header to an HTTP redirect destination.
        return None


def _validate_graph_url(url):
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname == "graph.microsoft.com"
                 and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
                 and parsed.path.startswith("/v1.0/") and not parsed.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise CalendarFetchError("Microsoft returned an unexpected calendar paging address.")


class GraphTransport:
    def get_json(self, url, headers, timeout=15):
        _validate_graph_url(url)
        try:
            with build_opener(_NoRedirect()).open(Request(url, headers=headers), timeout=timeout) as response:
                payload = response.read(8 * 1024 * 1024 + 1)
                if len(payload) > 8 * 1024 * 1024:
                    raise CalendarFetchError("Microsoft returned an oversized calendar response.")
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError("Unexpected response")
            return value
        except HTTPError as exc:
            messages = {
                401: "Microsoft calendar sign-in has expired. Connect again.",
                403: "Microsoft denied access to this calendar. Check read-only calendar consent and sharing permissions.",
                404: "This Microsoft calendar is no longer available.",
                429: "Microsoft is limiting calendar requests. Try refreshing shortly.",
            }
            raise CalendarFetchError(messages.get(exc.code, "Microsoft calendar service is temporarily unavailable.")) from None
        except (URLError, TimeoutError, OSError):
            raise CalendarFetchError("Microsoft calendars could not be reached. Check your connection.") from None
        except (ValueError, UnicodeError):
            raise CalendarFetchError("Microsoft returned an unreadable calendar response.") from None


def _load_zone_info(tz_name: str) -> ZoneInfo:
    if not tz_name or ".." in tz_name or tz_name.startswith(("/", "\\")):
        raise ZoneInfoNotFoundError(tz_name)
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        try:
            from bootstrap.runtime_bootstrap import bootstrap_timezone_data

            tz_dirs = bootstrap_timezone_data()
            for d_str in tz_dirs:
                candidate = Path(d_str) / Path(*tz_name.split("/"))
                if candidate.is_file():
                    with candidate.open("rb") as fobj:
                        return ZoneInfo.from_file(fobj, key=tz_name)
        except Exception:
            pass
        return ZoneInfo(tz_name)


def _datetime(value, toronto) -> datetime:
    if not isinstance(value, dict):
        raise ValueError("Missing date")
    raw = _text(value.get("dateTime"), 64)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        tz_name = _text(value.get("timeZone"), 100)
        if tz_name in {"Eastern Standard Time", TIME_ZONE}:
            parsed = parsed.replace(tzinfo=toronto)
        elif tz_name in {"UTC", "Etc/UTC"}:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            # A missing/unknown zone must not be guessed from the workstation.
            parsed = parsed.replace(tzinfo=_load_zone_info(tz_name))
    return parsed.astimezone(toronto)


def _safe_web_url(value) -> str:
    value = _text(value, 4096)
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def _holiday_key(title) -> str:
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())


class CalendarAgendaService:
    """No workbook dependency, network writes or disk-persisted agenda content.

    ``/me/calendars`` discovers owned calendars and readable shared custom
    calendars. Shared primary/group calendars visible only in Outlook may not
    be enumerated by Microsoft Graph and are not promised by this contract.
    """

    def __init__(self, profile_dir: Path, holiday_provider=None, now=None, *, auth=None, transport=None):
        self._auth = auth or CalendarAuth(profile_dir)
        self._transport = transport or GraphTransport()
        self._holiday_provider = holiday_provider
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._last_snapshot = None
        self._last_key = None

    def _clock(self):
        try:
            toronto = _load_zone_info(TIME_ZONE)
        except ZoneInfoNotFoundError:
            raise CalendarFetchError("Toronto time-zone data is missing from this installation.") from None
        value = self._now() if callable(self._now) else self._now
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise CalendarFetchError("Calendar time must include its time zone.")
        return value.astimezone(toronto), toronto

    def _pages(self, url, token, cancel_event):
        visited = set()
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "Prefer": _GRAPH_PREFER}
        for _ in range(_MAX_PAGES):
            check_cancelled(cancel_event)
            _validate_graph_url(url)
            if url in visited:
                raise CalendarFetchError("Microsoft returned a repeated calendar page.")
            visited.add(url)
            try:
                page = self._transport.get_json(url, headers=headers, timeout=15)
            except (CalendarFetchError, CalendarCancelled):
                raise
            except Exception:
                raise CalendarFetchError("Microsoft calendars could not be loaded. Check connectivity and permissions.") from None
            check_cancelled(cancel_event)
            if not isinstance(page, dict) or not isinstance(page.get("value"), list):
                raise CalendarFetchError("Microsoft returned an incomplete calendar response.")
            yield page["value"]
            url = page.get("@odata.nextLink")
            if not url:
                return
        raise CalendarFetchError("Microsoft returned too many calendar pages. Some entries could not be loaded.")

    def _event(self, raw, calendar, now, toronto):
        if not isinstance(raw, dict):
            raise ValueError("Invalid event")
        if raw.get("isCancelled") or (raw.get("responseStatus") or {}).get("response") == "declined":
            return None
        start, end = _datetime(raw.get("start"), toronto), _datetime(raw.get("end"), toronto)
        if end.astimezone(timezone.utc) <= start.astimezone(timezone.utc):
            raise ValueError("Invalid range")
        all_day = raw.get("isAllDay") is True
        holiday = all_day and _holiday_key(calendar["name"]) in _KNOWN_HOLIDAY_NAMES
        meeting = raw.get("onlineMeeting") or {}
        location = raw.get("location") or {}
        return {
            "id": calendar["id"] + ":" + (_text(raw.get("id"), 2048) or _text(raw.get("iCalUId"), 2048)),
            "uid": _text(raw.get("iCalUId"), 2048), "title": _text(raw.get("subject"), 4000) or "Untitled appointment",
            "start": start.isoformat(), "end": end.isoformat(), "date": start.date().isoformat(),
            "allDay": all_day, "sourceCalendars": [calendar["name"]],
            "location": _text(location.get("displayName"), 2000),
            "webUrl": _safe_web_url(raw.get("webLink")),
            "joinUrl": _safe_web_url(meeting.get("joinUrl") or raw.get("onlineMeetingUrl")),
            "isCurrent": not all_day and start.astimezone(timezone.utc) <= now.astimezone(timezone.utc) < end.astimezone(timezone.utc),
            "kind": "holiday" if holiday else "appointment",
        }

    @staticmethod
    def _merge_events(events):
        merged = []
        keys = {}
        for event in events:
            if event["kind"] == "holiday":
                key = ("holiday", _holiday_key(event["title"]), event["date"])
            elif event.get("uid"):
                key = ("appointment", event["uid"], event["start"])
            else:
                key = None  # equal titles/times are not sufficient meeting identity
            if key is not None and key in keys:
                target = keys[key]
                target["sourceCalendars"] = list(dict.fromkeys(target["sourceCalendars"] + event["sourceCalendars"]))
                for field in ("location", "webUrl", "joinUrl"):
                    if not target.get(field):
                        target[field] = event.get(field, "")
            else:
                merged.append(event)
                if key is not None:
                    keys[key] = event
        return merged

    @staticmethod
    def _bucket(events, now, toronto):
        today = now.date()
        last_day = today + timedelta(days=7)
        today_events, upcoming = [], []
        for event in events:
            start = datetime.fromisoformat(event["start"]).astimezone(toronto)
            end = datetime.fromisoformat(event["end"]).astimezone(toronto)
            if event["allDay"]:
                days = []
                cursor = max(start.date(), today)
                while cursor <= last_day and cursor < end.date():
                    days.append(cursor)
                    cursor += timedelta(days=1)
            elif end.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
                continue
            else:
                days = [max(start.date(), today)]
            for event_day in days:
                if not today <= event_day <= last_day:
                    continue
                entry = deepcopy(event)
                entry["date"] = event_day.isoformat()
                if len(days) > 1:
                    entry["id"] += ":" + event_day.isoformat()
                (today_events if event_day == today else upcoming).append(entry)
        sort_key = lambda event: (event["date"], not event["allDay"], datetime.fromisoformat(event["start"]).timestamp(), event["title"].casefold())
        return sorted(today_events, key=sort_key), sorted(upcoming, key=sort_key)

    @staticmethod
    def _config_key(config):
        return json.dumps(config, sort_keys=True)

    def _preserve_stale(self, snapshot, config):
        if self._last_snapshot is not None and self._last_key == self._config_key(config):
            previous = deepcopy(self._last_snapshot)
            previous.update(state=snapshot["state"], message=snapshot["message"], errors=snapshot["errors"], stale=True)
            return previous
        return snapshot

    def fetch(self, config, cancel_event=None):
        with self._lock:
            return self._fetch_locked(sanitize_calendar_config(config), cancel_event)

    def _fetch_locked(self, config, cancel_event, token=None, auth_failure=None):
        snapshot = empty_snapshot(config)
        try:
            check_cancelled(cancel_event)
            now, toronto = self._clock()
        except (CalendarFetchError, CalendarCancelled) as exc:
            snapshot.update(state="error", message=str(exc), errors=[str(exc)])
            return self._preserve_stale(snapshot, config)
        today = now.date()
        horizon = today + timedelta(days=7)
        start = datetime.combine(today, time.min, toronto)
        end = datetime.combine(horizon + timedelta(days=1), time.min, toronto)
        snapshot["asOf"] = now.isoformat()
        events, errors = [], []
        loaded_calendars = 0
        discovered = []
        if config["clientId"] and config["accountEmail"]:
            try:
                if auth_failure is not None:
                    raise auth_failure
                token_data = token or self._auth.get_token(config, cancel_event)
                if token_data.get("accountEmail", "").casefold() != config["accountEmail"].casefold():
                    raise CalendarAuthError("The saved Microsoft account differs from the configured calendar account.", "disconnected")
                access_token = token_data["access_token"]
                try:
                    for page in self._pages(GRAPH_ROOT + "/me/calendars?" + urlencode({"$select": "id,name,owner", "$top": 100}), access_token, cancel_event):
                        for raw in page:
                            if not isinstance(raw, dict) or not _text(raw.get("id"), 1024):
                                errors.append("Microsoft returned a calendar without a usable identity.")
                                continue
                            owner = raw.get("owner") or {}
                            discovered.append({
                                "id": _text(raw["id"], 1024), "name": _text(raw.get("name"), 1000) or "Microsoft calendar",
                                "owner": _text(owner.get("address"), 254), "source": "microsoft365",
                                "enabled": raw["id"] not in config["disabledCalendarIds"],
                            })
                except CalendarFetchError as exc:
                    errors.append(str(exc))
                # Pagination may contain a repeated calendar; fetch it once.
                discovered = list({calendar["id"]: calendar for calendar in discovered}.values())
                snapshot["calendars"].extend(discovered)
                for calendar in discovered:
                    if not calendar["enabled"]:
                        continue
                    url = GRAPH_ROOT + "/me/calendars/" + quote(calendar["id"], safe="") + "/calendarView?" + urlencode({
                        "startDateTime": start.isoformat(), "endDateTime": end.isoformat(), "$top": 500,
                        "$select": "id,iCalUId,subject,start,end,isAllDay,isCancelled,responseStatus,location,webLink,onlineMeeting,onlineMeetingUrl",
                    })
                    try:
                        for page in self._pages(url, access_token, cancel_event):
                            for raw in page:
                                try:
                                    event = self._event(raw, calendar, now, toronto)
                                    if event is not None:
                                        events.append(event)
                                except (ValueError, TypeError, AttributeError, ZoneInfoNotFoundError):
                                    errors.append("An entry in " + calendar["name"] + " has unreadable dates or details and was omitted.")
                        loaded_calendars += 1
                    except CalendarFetchError as exc:
                        errors.append(calendar["name"] + ": " + str(exc))
                snapshot.update(state="ready", message="Microsoft 365 calendars refreshed.")
            except CalendarCancelled:
                snapshot.update(state="error", message="Calendar operation cancelled.", errors=["Calendar operation cancelled."])
                return self._preserve_stale(snapshot, config)
            except CalendarAuthError as exc:
                snapshot.update(state=exc.state, message=str(exc))
                if exc.state == "error":
                    errors.append(str(exc))
            except Exception:
                snapshot.update(state="error", message="Microsoft calendars could not be loaded. Check your connection and account settings.")
                errors.append(snapshot["message"])
        if self._holiday_provider is not None:
            try:
                check_cancelled(cancel_event)
                holidays = self._holiday_provider.fetch(config, today, horizon, cancel_event)
                check_cancelled(cancel_event)
                snapshot["calendars"].extend(holidays.get("calendars", []))
                events.extend(holidays.get("events", []))
                errors.extend(holidays.get("errors", []))
            except CalendarCancelled:
                snapshot.update(state="error", message="Calendar operation cancelled.", errors=["Calendar operation cancelled."])
                return self._preserve_stale(snapshot, config)
            except Exception:
                errors.append("Holiday calendars could not be refreshed.")
        snapshot["errors"] = list(dict.fromkeys(errors))
        snapshot["today"], snapshot["next7Days"] = self._bucket(self._merge_events(events), now, toronto)
        if snapshot["state"] == "ready" and errors:
            snapshot.update(state="partial" if loaded_calendars or events else "error",
                            message="Some calendar sources could not be loaded. The agenda may be incomplete.")
        if snapshot["state"] == "error" and not events:
            snapshot = self._preserve_stale(snapshot, config)
        if snapshot["state"] in {"ready", "partial"}:
            self._last_snapshot, self._last_key = deepcopy(snapshot), self._config_key(config)
        return snapshot

    def connect(self, config, challenge_callback, cancel_event):
        with self._lock:
            config = sanitize_calendar_config(config)
            if not config["clientId"] or not config["accountEmail"]:
                return self._fetch_locked(config, cancel_event)
            try:
                token = self._auth.connect(config, challenge_callback, cancel_event)
            except CalendarAuthError as exc:
                return self._fetch_locked(config, cancel_event, auth_failure=exc)
            except Exception:
                return self._fetch_locked(config, cancel_event, auth_failure=CalendarAuthError("Microsoft sign-in could not complete."))
            return self._fetch_locked(config, cancel_event, token=token)

    def disconnect(self):
        with self._lock:
            try:
                self._auth.disconnect()
            finally:
                self._last_snapshot = None
                self._last_key = None
