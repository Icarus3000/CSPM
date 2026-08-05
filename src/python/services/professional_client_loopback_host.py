"""Explicit-start local HTTP host for the future Professional client proof.

The host is intentionally not connected to application startup. Callers must
construct and start it explicitly, provide the in-memory session token to the
launched local client through a protected handoff, and stop it when the proof
session ends.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import secrets
from threading import Thread, current_thread
from typing import Any
from urllib.parse import urlsplit

from services.professional_client_service import (
    ACTION_NAMES,
    QUERY_NAMES,
    LocalLoopbackBoundaryConfig,
    ProfessionalClientService,
)


@dataclass(frozen=True)
class ProfessionalClientLoopbackHostInfo:
    host: str
    port: int
    query_path: str
    action_path: str
    event_path: str
    event_transport_status: str = "websocket_deferred"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "baseUrl": self.base_url,
            "queryPath": self.query_path,
            "actionPath": self.action_path,
            "eventPath": self.event_path,
            "eventTransportStatus": self.event_transport_status,
        }


def _transport_error(
    *,
    code: str,
    message: str,
    request_id: str = "",
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "ok": False,
        "payload": {},
        "errors": [{"code": code, "message": message}],
        "warnings": [],
        "validation": {},
    }


class ProfessionalClientLoopbackHost:
    """Token-protected HTTP JSON host bound strictly to IPv4 loopback."""

    def __init__(
        self,
        service: ProfessionalClientService,
        *,
        config: LocalLoopbackBoundaryConfig | None = None,
        session_token: str | None = None,
    ) -> None:
        self.service = service
        self.config = config or service.config
        self._session_token = (
            secrets.token_urlsafe(32)
            if session_token is None
            else str(session_token).strip()
        )
        if len(self._session_token) < 32:
            raise ValueError("Professional client session tokens must be at least 32 characters.")
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._info: ProfessionalClientLoopbackHostInfo | None = None

    @property
    def session_token(self) -> str:
        """Return the in-memory token for a protected parent/child handoff."""

        return self._session_token

    @property
    def is_running(self) -> bool:
        return bool(self._server is not None and self._thread is not None and self._thread.is_alive())

    @property
    def info(self) -> ProfessionalClientLoopbackHostInfo | None:
        return self._info

    def start(self) -> ProfessionalClientLoopbackHostInfo:
        if self.is_running and self._info is not None:
            return self._info

        self._validate_config()
        handler_type = self._build_handler()
        server = ThreadingHTTPServer((self.config.host, int(self.config.port)), handler_type)
        server.daemon_threads = True

        bound_host, bound_port = server.server_address[:2]
        info = ProfessionalClientLoopbackHostInfo(
            host=str(bound_host),
            port=int(bound_port),
            query_path=self.config.query_path,
            action_path=self.config.action_path,
            event_path=self.config.event_path,
        )
        thread = Thread(
            target=server.serve_forever,
            name="CSPM-ProfessionalClientLoopback",
            daemon=True,
        )

        self._server = server
        self._thread = thread
        self._info = info
        thread.start()
        return info

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        self._info = None

        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread is not current_thread():
            thread.join(timeout=5.0)

    def __enter__(self) -> ProfessionalClientLoopbackHost:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

    def _validate_config(self) -> None:
        if self.config.host != "127.0.0.1":
            raise ValueError("Professional client host must bind to 127.0.0.1 only.")
        if self.config.allow_lan_binding:
            raise ValueError("Professional client LAN binding is not permitted.")
        if not self.config.require_session_token:
            raise ValueError("Professional client loopback HTTP requires a session token.")
        if int(self.config.port) != 0:
            raise ValueError("Professional client loopback HTTP must use a random per-launch port.")
        if int(self.config.max_request_bytes) <= 0:
            raise ValueError("Professional client max request size must be positive.")

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        host = self

        class ProfessionalClientRequestHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "CSPMProfessionalLoopback/0.1"

            def log_message(self, format_string: str, *args: object) -> None:
                # Request payloads and tokens must not leak into default HTTP logs.
                return

            def do_POST(self) -> None:
                path = urlsplit(self.path).path
                if path not in (host.config.query_path, host.config.action_path):
                    self._write_json(
                        404,
                        _transport_error(code="route_not_found", message="Unknown local service route."),
                    )
                    return
                if not self._is_authorized():
                    self._write_json(
                        401,
                        _transport_error(
                            code="unauthorized",
                            message="A valid Professional client session token is required.",
                        ),
                    )
                    return

                content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._write_json(
                        415,
                        _transport_error(
                            code="unsupported_media_type",
                            message="Professional client requests must use application/json.",
                        ),
                    )
                    return

                try:
                    content_length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    content_length = -1
                if content_length < 0:
                    self._write_json(
                        400,
                        _transport_error(code="invalid_content_length", message="Content-Length is invalid."),
                    )
                    return
                if content_length > int(host.config.max_request_bytes):
                    self.close_connection = True
                    self._write_json(
                        413,
                        _transport_error(code="request_too_large", message="Request body exceeds the local limit."),
                    )
                    return

                try:
                    raw_body = self.rfile.read(content_length)
                    envelope = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._write_json(
                        400,
                        _transport_error(code="invalid_json", message="Request body is not valid UTF-8 JSON."),
                    )
                    return
                if not isinstance(envelope, dict):
                    self._write_json(
                        400,
                        _transport_error(code="invalid_envelope", message="Request JSON must be an object."),
                    )
                    return

                action = str(envelope.get("action") or "")
                if path == host.config.query_path and action in ACTION_NAMES:
                    self._write_channel_mismatch(envelope, "query")
                    return
                if path == host.config.action_path and action in QUERY_NAMES:
                    self._write_channel_mismatch(envelope, "action")
                    return

                response = host.service.handle_http_json_request(envelope)
                self._write_json(200, response)

            def do_GET(self) -> None:
                path = urlsplit(self.path).path
                if path == host.config.event_path:
                    if not self._is_authorized():
                        self._write_json(
                            401,
                            _transport_error(
                                code="unauthorized",
                                message="A valid Professional client session token is required.",
                            ),
                        )
                        return
                    self._write_json(
                        501,
                        _transport_error(
                            code="websocket_deferred",
                            message="The WebSocket event stream is not implemented in this HTTP proof slice.",
                        ),
                    )
                    return
                self._write_json(
                    405,
                    _transport_error(code="method_not_allowed", message="Use POST for local service requests."),
                )

            def do_OPTIONS(self) -> None:
                self._write_json(
                    403,
                    _transport_error(
                        code="cors_denied",
                        message="Cross-origin browser access is denied by default.",
                    ),
                )

            def _is_authorized(self) -> bool:
                provided = str(self.headers.get("Authorization") or "")
                expected = f"Bearer {host.session_token}"
                return hmac.compare_digest(provided, expected)

            def _write_channel_mismatch(self, envelope: dict[str, Any], expected_channel: str) -> None:
                self._write_json(
                    400,
                    _transport_error(
                        request_id=str(envelope.get("requestId") or ""),
                        code="channel_mismatch",
                        message=f"Request action does not belong on the {expected_channel} channel.",
                    ),
                )

            def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=True, default=str).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

        return ProfessionalClientRequestHandler
