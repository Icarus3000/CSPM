"""Framework-neutral service boundary for the future Professional client.

This module is intentionally transport-shaped but dependency-free. The
explicit-start loopback HTTP host delegates to this dispatcher without moving
Client Directory/Profile behavior into network handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


CLIENT_DIRECTORY_QUERY = "listClientDirectory"
CLIENT_PROFILE_QUERY = "getClientProfile"
OPEN_WORKSPACE_ACTION = "openWorkspace"
OPEN_CLIENT_PROFILE_ACTION = "openClientProfile"
QUERY_NAMES = frozenset((CLIENT_DIRECTORY_QUERY, CLIENT_PROFILE_QUERY))
ACTION_NAMES = frozenset((OPEN_WORKSPACE_ACTION, OPEN_CLIENT_PROFILE_ACTION))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LocalLoopbackBoundaryConfig:
    """Selected local boundary for the first external Professional proof."""

    host: str = "127.0.0.1"
    port: int = 0
    query_path: str = "/v1/query"
    action_path: str = "/v1/action"
    event_path: str = "/v1/events"
    require_session_token: bool = True
    allow_lan_binding: bool = False
    enabled_by_default: bool = False
    max_request_bytes: int = 1_048_576

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "queryPath": self.query_path,
            "actionPath": self.action_path,
            "eventPath": self.event_path,
            "requireSessionToken": self.require_session_token,
            "allowLanBinding": self.allow_lan_binding,
            "enabledByDefault": self.enabled_by_default,
            "maxRequestBytes": self.max_request_bytes,
        }


@dataclass(frozen=True)
class ProfessionalClientEvent:
    sequence: int
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    actor: str = ""
    timestamp_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "name": self.name,
            "payload": dict(self.payload),
            "requestId": self.request_id,
            "actor": self.actor,
            "timestampUtc": self.timestamp_utc,
        }


class ProfessionalClientEventBroker:
    """In-memory event source for the future WebSocket event stream."""

    def __init__(self) -> None:
        self._events: list[ProfessionalClientEvent] = []
        self._next_sequence = 1
        self._lock = RLock()

    def publish(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        request_id: str = "",
        actor: str = "",
    ) -> ProfessionalClientEvent:
        with self._lock:
            event = ProfessionalClientEvent(
                sequence=self._next_sequence,
                name=str(name or ""),
                payload=dict(payload or {}),
                request_id=str(request_id or ""),
                actor=str(actor or ""),
            )
            self._next_sequence += 1
            self._events.append(event)
            return event

    def drain_events(self, after_sequence: int = 0) -> list[dict[str, Any]]:
        floor = int(after_sequence or 0)
        with self._lock:
            return [event.to_dict() for event in self._events if event.sequence > floor]


class ProfessionalClientService:
    """Envelope dispatcher for the selected Professional local service boundary."""

    def __init__(
        self,
        backend: Any,
        *,
        event_broker: ProfessionalClientEventBroker | None = None,
        config: LocalLoopbackBoundaryConfig | None = None,
    ) -> None:
        self._backend = backend
        self.events = event_broker or ProfessionalClientEventBroker()
        self.config = config or LocalLoopbackBoundaryConfig()
        self._dispatch_lock = RLock()
        self._handlers: dict[str, Callable[[dict[str, Any], str, str], dict[str, Any]]] = {
            CLIENT_DIRECTORY_QUERY: self._handle_list_client_directory,
            CLIENT_PROFILE_QUERY: self._handle_get_client_profile,
            OPEN_WORKSPACE_ACTION: self._handle_open_workspace,
            OPEN_CLIENT_PROFILE_ACTION: self._handle_open_client_profile,
        }

    def handle_http_json_request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a `/v1/query` or `/v1/action` JSON envelope."""

        with self._dispatch_lock:
            return self._handle_http_json_request(envelope)

    def _handle_http_json_request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        request_id = str((envelope or {}).get("requestId") or "")
        actor = str((envelope or {}).get("actor") or "")
        validation = self._validate_request_envelope(envelope)
        if validation:
            return self._failure(
                request_id=request_id,
                actor=actor,
                code="invalid_request",
                message="Request envelope is incomplete.",
                validation=validation,
            )

        action = str(envelope.get("action") or "")
        payload = dict(envelope.get("payload") or {})
        handler = self._handlers.get(action)
        if handler is None:
            return self._failure(
                request_id=request_id,
                actor=actor,
                code="unknown_action",
                message=f"Unsupported Professional client action: {action}",
            )

        try:
            result_payload = handler(payload, request_id, actor)
        except Exception:
            return self._failure(
                request_id=request_id,
                actor=actor,
                code="dispatch_failed",
                message="Professional client request failed.",
            )

        return self._response(request_id=request_id, ok=True, payload=result_payload)

    def _validate_request_envelope(self, envelope: Any) -> dict[str, list[str]]:
        missing: list[str] = []
        invalid: list[str] = []
        if not isinstance(envelope, dict):
            return {"missing": ["requestId", "action", "payload", "actor", "timestampUtc"], "invalid": ["envelope"]}
        for field_name in ("requestId", "action", "payload", "actor", "timestampUtc"):
            if field_name not in envelope:
                missing.append(field_name)
        if "payload" in envelope and not isinstance(envelope.get("payload"), dict):
            invalid.append("payload")
        return {"missing": missing, "invalid": invalid} if missing or invalid else {}

    def _handle_list_client_directory(
        self,
        payload: dict[str, Any],
        request_id: str,
        actor: str,
    ) -> dict[str, Any]:
        rows = [dict(row) for row in self._call_backend("listClientDirectory", "list_client_directory")]
        active_only = bool(payload.get("activeOnly", False))
        query = str(payload.get("query", "") or "").strip().lower()

        if active_only:
            rows = [row for row in rows if str(row.get("status", "") or "").strip().lower() in ("", "active")]
        if query:
            rows = [row for row in rows if self._row_matches_query(row, query)]

        result = {
            "rows": rows,
            "count": len(rows),
            "activeOnly": active_only,
            "query": query,
        }
        self.events.publish(
            "clientDirectoryRefreshed",
            {"count": len(rows), "activeOnly": active_only, "query": query},
            request_id=request_id,
            actor=actor,
        )
        return result

    def _handle_get_client_profile(
        self,
        payload: dict[str, Any],
        request_id: str,
        actor: str,
    ) -> dict[str, Any]:
        client_key = self._client_key_from_payload(payload)
        profile = dict(self._call_backend("getClientProfile", "get_client_profile", client_key) or {})
        return {"profile": profile}

    def _handle_open_workspace(
        self,
        payload: dict[str, Any],
        request_id: str,
        actor: str,
    ) -> dict[str, Any]:
        tab = dict(payload.get("tab") or payload.get("state") or {})
        tab_id = str(payload.get("tabId") or tab.get("id") or "")
        self.events.publish("workspaceOpened", dict(payload), request_id=request_id, actor=actor)
        if tab_id:
            self.events.publish("tabActivated", {"tabId": tab_id}, request_id=request_id, actor=actor)
        return {"workspace": dict(payload)}

    def _handle_open_client_profile(
        self,
        payload: dict[str, Any],
        request_id: str,
        actor: str,
    ) -> dict[str, Any]:
        client_key = self._client_key_from_payload(payload)
        profile = dict(self._call_backend("getClientProfile", "get_client_profile", client_key) or {})
        client = dict(profile.get("client") or {})
        client_id = str(payload.get("clientId") or client.get("clientId") or client_key or "").strip()
        client_name = str(payload.get("clientName") or client.get("clientName") or client_id or "").strip()
        tab = self._client_profile_tab(client_id=client_id, client_name=client_name)

        self.events.publish("workspaceOpened", {"tab": tab}, request_id=request_id, actor=actor)
        self.events.publish("tabActivated", {"tabId": tab["id"]}, request_id=request_id, actor=actor)
        self.events.publish(
            "clientProfileOpened",
            {"clientId": client_id, "clientName": client_name, "tabId": tab["id"]},
            request_id=request_id,
            actor=actor,
        )
        return {"profile": profile, "tab": tab}

    def _client_profile_tab(self, *, client_id: str, client_name: str) -> dict[str, Any]:
        entity_id = client_id or client_name
        title_name = client_name or client_id or "Client"
        tab_id = f"client-profile:{entity_id}"
        return {
            "id": tab_id,
            "title": f"Client: {title_name}",
            "moduleId": "clients",
            "moduleTitle": "Clients & Matters",
            "tileIndex": 0,
            "nodeId": "A03",
            "route": "/clients/profile",
            "tabType": "client",
            "singleInstance": False,
            "singleInstanceKey": tab_id,
            "dirty": False,
            "pinned": False,
            "entityType": "client",
            "entityId": entity_id,
            "entityTitle": title_name,
            "params": {"clientId": client_id, "clientName": client_name},
        }

    def _client_key_from_payload(self, payload: dict[str, Any]) -> str:
        return str(
            payload.get("clientId")
            or payload.get("clientName")
            or payload.get("clientKey")
            or payload.get("entityId")
            or ""
        ).strip()

    def _row_matches_query(self, row: dict[str, Any], query: str) -> bool:
        haystack_fields = (
            "clientId",
            "clientName",
            "legalName",
            "displayName",
            "parentName",
            "primaryEmail",
        )
        return any(query in str(row.get(field_name, "") or "").lower() for field_name in haystack_fields)

    def _call_backend(self, camel_name: str, snake_name: str, *args: Any) -> Any:
        for method_name in (camel_name, snake_name):
            method = getattr(self._backend, method_name, None)
            if callable(method):
                return method(*args)
        raise AttributeError(f"Backend does not expose {camel_name} or {snake_name}")

    def _failure(
        self,
        *,
        request_id: str,
        actor: str,
        code: str,
        message: str,
        validation: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        error = {"code": code, "message": message}
        self.events.publish(
            "uiFailureReported",
            {"code": code, "message": message, "validation": dict(validation or {})},
            request_id=request_id,
            actor=actor,
        )
        return self._response(
            request_id=request_id,
            ok=False,
            payload={},
            errors=[error],
            validation=validation or {},
        )

    def _response(
        self,
        *,
        request_id: str,
        ok: bool,
        payload: dict[str, Any],
        errors: list[dict[str, str]] | None = None,
        warnings: list[dict[str, str]] | None = None,
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "requestId": str(request_id or ""),
            "ok": bool(ok),
            "payload": dict(payload or {}),
            "errors": list(errors or []),
            "warnings": list(warnings or []),
            "validation": dict(validation or {}),
        }
