from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

if __package__ in (None, ""):
    _THIS_FILE = Path(__file__).resolve()
    _PYTHON_ROOT = _THIS_FILE.parent
    if str(_PYTHON_ROOT) not in sys.path:
        sys.path.insert(0, str(_PYTHON_ROOT))

from services.paths import AppPaths
from services.quick_expense_service import QuickExpenseService

logger = logging.getLogger("cspm.quick_expense")

DEFAULT_PORT = int(os.environ.get("CSPM_QUICK_EXPENSE_PORT", "24820"))

PRIMARY_QE_ORIGIN = os.environ.get("CSPM_QE_PRIMARY_URL", "https://officenew.tail38e9b9.ts.net").rstrip("/")


def _is_primary_qe_host() -> bool:
    if os.environ.get("CSPM_QE_FORCE_LOCAL", "").strip() in ("1", "true", "True"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST", "").strip():
        return True
    return socket.gethostname().strip().lower() == "officenew"


def _peer_cache_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CSPM" / "working" / "data" / "QuickExpense_Sync" / "peer_cache"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def _resolve_template_dir() -> Path:
    paths = AppPaths(root=AppPaths.project_root())
    candidates = [
        paths.root / "src" / "templates" / "quick_expense",
        Path(__file__).resolve().parents[1] / "templates" / "quick_expense",
        Path(__file__).resolve().parents[2] / "src" / "templates" / "quick_expense",
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(getattr(sys, "_MEIPASS"))
        candidates.insert(0, meipass / "src" / "templates" / "quick_expense")
        candidates.insert(1, meipass / "templates" / "quick_expense")
    for cand in candidates:
        if cand.exists():
            return cand
    return candidates[0]


def is_port_listening(port: int = DEFAULT_PORT, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex((host, port)) == 0



_QE_VER_CACHE: Dict[str, Any] = {"sig": None, "ver": "qe-init"}


def _compute_live_qe_version(template_dir: Path) -> str:
    try:
        tracked = [
            template_dir / "index.html",
            template_dir / "sw.js",
            Path(__file__).resolve(),
            Path(__file__).resolve().parent / "services" / "quick_expense_service.py",
        ]
        sig = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in tracked if p.exists())
        if _QE_VER_CACHE.get("sig") == sig:
            return str(_QE_VER_CACHE["ver"])
        h = hashlib.sha256()
        for p in tracked:
            if p.exists():
                h.update(p.read_bytes())
        ver = "qe-" + h.hexdigest()[:10]
        _QE_VER_CACHE["sig"] = sig
        _QE_VER_CACHE["ver"] = ver
        return ver
    except Exception:
        return "qe-fallback"


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.3)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class QuickExpenseRequestHandler(BaseHTTPRequestHandler):
    service: QuickExpenseService
    template_dir: Path
    on_data_changed: Optional[Any] = None

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("QuickExpenseHTTP: " + format, *args)

    def _get_client_meta(self) -> Dict[str, Any]:
        from services.quick_expense_session import parse_client_device
        ua = self.headers.get("User-Agent", "")
        device = parse_client_device(ua)
        client_ip = (
            self.headers.get("X-Forwarded-For")
            or self.headers.get("X-Real-IP")
            or (self.client_address[0] if hasattr(self, "client_address") else "127.0.0.1")
        ).split(",")[0].strip()
        return {"device": device, "client_ip": client_ip, "userAgent": ua}

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        self.close_connection = True
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        ver = _compute_live_qe_version(self.template_dir)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("X-App-Version", ver)
        self.send_header("Access-Control-Expose-Headers", "X-App-Version")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, content_type: str, inject_version: bool = False) -> None:
        self.close_connection = True
        if not file_path.exists():
            self.send_error(404, "File not found")
            return
        ver = _compute_live_qe_version(self.template_dir)
        if inject_version:
            txt = file_path.read_text(encoding="utf-8").replace("__LPN_APP_VERSION__", ver)
            data = txt.encode("utf-8")
        else:
            data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0" if inject_version else "no-cache")
        self.send_header("X-App-Version", ver)
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.close_connection = True
        self.send_response(204)
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()


    def _try_federate_to_primary(self, method: str, raw_body: bytes = b"") -> bool:
        """On secondary workstations (e.g. Omnibook / iMacFedora), transparently federate
        live /api/* data calls to canonical OFFICENEW (https://officenew.tail38e9b9.ts.net)
        so mobile, OFFICENEW, and Omnibook always share 100% real-time unified data, while
        caching GET responses locally for seamless offline failover."""
        if _is_primary_qe_host():
            return False
        if self.headers.get("X-CSPM-No-Proxy") == "1":
            return False
        if not PRIMARY_QE_ORIGIN:
            return False

        import urllib.request
        import urllib.error

        target_url = f"{PRIMARY_QE_ORIGIN}{self.path}"
        cache_key = hashlib.sha256(f"{method}:{self.path}".encode("utf-8")).hexdigest()[:24]
        cache_file = _peer_cache_dir() / f"{cache_key}.bin"
        meta_file = _peer_cache_dir() / f"{cache_key}.json"

        headers = {
            "X-CSPM-No-Proxy": "1",
            "User-Agent": self.headers.get("User-Agent") or "CSPM-QuickExpense-Peer/1.0",
            "Accept": self.headers.get("Accept") or "application/json",
        }
        if method == "POST":
            headers["Content-Type"] = self.headers.get("Content-Type") or "application/json; charset=utf-8"

        req = urllib.request.Request(
            target_url,
            data=raw_body if method == "POST" else None,
            headers=headers,
            method=method,
        )
        try:
            timeout_sec = 4.5 if method == "GET" else 8.0
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                status = resp.status
                ctype = resp.headers.get("Content-Type") or "application/json; charset=utf-8"
                data = resp.read()
                if method == "GET" and status == 200 and data:
                    try:
                        cache_file.write_bytes(data)
                        meta_file.write_text(json.dumps({"contentType": ctype, "path": self.path, "ts": time.time()}), encoding="utf-8")
                    except Exception:
                        pass
                ver = _compute_live_qe_version(self.template_dir)
                self.close_connection = True
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("X-App-Version", ver)
                self.send_header("X-CSPM-Data-Source", "officenew-live")
                self.send_header("Access-Control-Expose-Headers", "X-App-Version, X-CSPM-Data-Source")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
                return True
        except urllib.error.HTTPError as http_err:
            # Propagate genuine 4xx responses (e.g. wrong PIN or 404 PDF) directly from primary
            if 400 <= http_err.code < 500:
                try:
                    err_body = http_err.read()
                    ctype = http_err.headers.get("Content-Type") or "application/json; charset=utf-8"
                    ver = _compute_live_qe_version(self.template_dir)
                    self.close_connection = True
                    self.send_response(http_err.code)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(err_body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-App-Version", ver)
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(err_body)
                    return True
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Primary peer %s unreachable (%s); checking peer cache / local failover", target_url, exc)

        # If GET and we have a recent cached snapshot from primary, serve it cleanly while offline
        if method == "GET" and cache_file.exists() and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                data = cache_file.read_bytes()
                ver = _compute_live_qe_version(self.template_dir)
                self.close_connection = True
                self.send_response(200)
                self.send_header("Content-Type", meta.get("contentType") or "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-App-Version", ver)
                self.send_header("X-CSPM-Data-Source", "peer-cache-offline")
                self.send_header("Access-Control-Expose-Headers", "X-App-Version, X-CSPM-Data-Source")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
                return True
            except Exception:
                pass
        return False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_file(self.template_dir / "index.html", "text/html; charset=utf-8", inject_version=True)
            return
        if path == "/manifest.json":
            self._send_file(self.template_dir / "manifest.json", "application/manifest+json; charset=utf-8")
            return
        if path in ("/sw.js",):
            self._send_file(self.template_dir / "sw.js", "application/javascript; charset=utf-8", inject_version=True)
            return
        if path == "/icon.svg":
            self._send_file(self.template_dir / "icon.svg", "image/svg+xml; charset=utf-8")
            return
        if path in ("/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png"):
            self._send_file(self.template_dir / path.lstrip("/"), "image/png")
            return
        if path == "/favicon.ico":
            self._send_file(self.template_dir / "favicon.ico", "image/x-icon")
            return

        if path == "/api/version":
            ver = _compute_live_qe_version(self.template_dir)
            self._send_json({"ok": True, "app": "Quick Expense", "version": ver, "appVersion": ver})
            return

        if path == "/api/health":
            ver = _compute_live_qe_version(self.template_dir)
            self._send_json(
                {
                    "ok": True,
                    "service": "cspm-quick-expense",
                    "version": ver,
                    "appVersion": ver,
                    "lanIp": get_lan_ip(),
                    "port": self.server.server_port,
                }
            )
            return

        if path.startswith("/api/") and self._try_federate_to_primary("GET"):
            return

        user_id = (qs.get("userId") or ["deborah"])[0]

        if path == "/api/session/active":
            s = self.service.get_active_session(user_id=user_id, client_meta=self._get_client_meta())
            self._send_json({"ok": True, "session": s})
            return

        if path == "/api/bootstrap":
            res = self.service.get_bootstrap_data(user_id=user_id)
            self._send_json(res)
            return

        if path == "/api/entries":
            period = (qs.get("period") or ["today"])[0]
            date_from = (qs.get("dateFrom") or [""])[0]
            date_to = (qs.get("dateTo") or [""])[0]
            stream_id = (qs.get("streamId") or [""])[0]
            entries = self.service.list_entries(
                user_id=user_id,
                period=period,
                date_from=date_from,
                date_to=date_to,
                stream_id=stream_id,
            )
            self._send_json({"ok": True, "entries": entries})
            return

        if path == "/api/report":
            period = (qs.get("period") or ["today"])[0]
            date_from = (qs.get("dateFrom") or [""])[0]
            date_to = (qs.get("dateTo") or [""])[0]
            stream_id = (qs.get("streamId") or ["ALL"])[0]
            rep = self.service.build_report(
                user_id=user_id,
                period=period,
                date_from=date_from,
                date_to=date_to,
                stream_id=stream_id,
            )
            self._send_json(rep)
            return

        if path == "/api/docket/matters":
            query = (qs.get("query") or [""])[0]
            matter_id = (qs.get("matterId") or [""])[0]
            period = (qs.get("period") or [""])[0]
            res = self.service.list_docket_matters(
                user_id=user_id,
                query=query,
                matter_id=matter_id,
                period=period,
            )
            self._send_json(res)
            return

        if path == "/api/wip-ar":
            res = self.service.get_wip_and_ar_overview(user_id=user_id)
            self._send_json(res)
            return

        if path == "/api/tax-snapshot":
            res = self.service.get_tax_and_shl_snapshot(user_id=user_id)
            self._send_json(res)
            return

        if path == "/api/receipt/file":
            receipt_id = (qs.get("receiptId") or [""])[0]
            txn_id = (qs.get("transactionId") or [""])[0]
            info = self.service.get_receipt_file_info(user_id=user_id, receipt_id=receipt_id, transaction_id=txn_id)
            if not info:
                self.send_error(404, "Receipt file not found")
                return
            f_path, mime_type, _ = info
            self._send_file(f_path, mime_type)
            return

        if path == "/api/invoice/pdf":
            invoice_num = (qs.get("invoice") or qs.get("invoiceNumber") or [""])[0]
            info = self.service.resolve_invoice_pdf(user_id=user_id, invoice_number=invoice_num)
            if not info:
                self.send_error(404, f"PDF for invoice {invoice_num} not found")
                return
            pdf_path, _ = info
            self._send_file(pdf_path, "application/pdf")
            return

        if path == "/api/payment/invoices":
            query = (qs.get("query") or [""])[0]
            party_type = (qs.get("partyType") or [""])[0]
            party_value = (qs.get("partyValue") or [""])[0]
            include_paid = (qs.get("includePaid") or ["0"])[0] in ("1", "true", "True")
            force_refresh = (qs.get("refresh") or ["0"])[0] in ("1", "true", "True")
            res = self.service.search_payment_invoices(
                user_id=user_id,
                query=query,
                party_type=party_type,
                party_value=party_value,
                include_paid=include_paid,
                force_refresh=force_refresh,
            )
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length") or "0")
        raw_bytes = self.rfile.read(length) if length > 0 else b"{}"
        if path.startswith("/api/") and self._try_federate_to_primary("POST", raw_bytes):
            return
        raw_body = raw_bytes.decode("utf-8")
        try:
            body = json.loads(raw_body or "{}")
        except Exception:
            self._send_json({"ok": False, "message": "Invalid JSON body."}, status=400)
            return

        if path == "/api/login":
            res = self.service.authenticate(
                username=str(body.get("username") or ""),
                pin=str(body.get("pin") or ""),
            )
            self._send_json(res)
            return

        if path == "/api/session/complete":
            user_id = str(body.get("userId") or "deborah")
            reason = str(body.get("reason") or "Operator Clicked Finish Session")
            force_send = bool(body.get("forceSend", False))
            res = self.service.complete_session(
                user_id=user_id,
                reason=reason,
                force_send=force_send,
                client_meta=self._get_client_meta(),
            )
            self._send_json(res)
            return

        if path == "/api/save":
            user_id = str(body.get("userId") or "deborah")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.save_entry(user_id=user_id, payload=payload)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/delete":
            user_id = str(body.get("userId") or "deborah")
            txn_id = str(body.get("transactionId") or "")
            res = self.service.delete_entry(user_id=user_id, transaction_id=txn_id)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/docket/save":
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.save_docket_entry(user_id=user_id, payload=payload)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/docket/delete":
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.delete_docket_entry(user_id=user_id, payload=payload)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/payment/post":
            user_id = str(body.get("userId") or "deborah")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.post_payment_entry(user_id=user_id, payload=payload)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/receipt/scan":
            user_id = str(body.get("userId") or "deborah")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.scan_and_stage_receipt(user_id=user_id, payload=payload)
            self._send_json(res)
            return

        if path == "/api/receipt/attach":
            user_id = str(body.get("userId") or "deborah")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.attach_receipt_to_entry(user_id=user_id, payload=payload)
            self._send_json(res)
            return

        if path == "/api/voice/parse":
            user_id = str(body.get("userId") or "deborah")
            transcript = str(body.get("transcript") or "")
            current_mode = str(body.get("currentMode") or "Expense")
            res = self.service.parse_voice_command(
                user_id=user_id,
                transcript=transcript,
                current_mode=current_mode,
            )
            self._send_json(res)
            return

        if path == "/api/invoice/preview":
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.preview_mobile_invoice(user_id=user_id, payload=payload)
            self._send_json(res)
            return

        if path == "/api/invoice/finalize":
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.finalize_mobile_invoice(user_id=user_id, payload=payload)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path == "/api/invoice/reverse":
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            inv_num = str(
                payload.get("invoiceNumber")
                or payload.get("invoice")
                or body.get("invoiceNumber")
                or body.get("invoice")
                or ""
            )
            res = self.service.reverse_mobile_invoice(user_id=user_id, invoice_number=inv_num)
            if res.get("ok") and callable(getattr(self, "on_data_changed", None)):
                try:
                    self.on_data_changed()
                except Exception:
                    pass
            self._send_json(res)
            return

        if path in ("/api/matter/create", "/api/docket/create-matter"):
            user_id = str(body.get("userId") or "cory")
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            res = self.service.create_quick_matter(user_id=user_id, payload=payload)
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found")


class QuickExpenseServerDaemon:
    """In-process background HTTP server for CSPM Quick Expense."""

    def __init__(
        self,
        service: Optional[QuickExpenseService] = None,
        port: int = DEFAULT_PORT,
        on_data_changed: Optional[Any] = None,
    ):
        self.service = service or QuickExpenseService()
        self.port = port
        self.on_data_changed = on_data_changed
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._idle_thread: Optional[threading.Thread] = None

    def _run_idle_session_checker(self) -> None:
        """Background thread checking every 30s: if an active session has entries
        and has been idle for >= 10 minutes (600s), automatically complete & email report."""
        while not self._stop_event.is_set():
            try:
                time.sleep(30.0)
                if self._stop_event.is_set():
                    break
                self.service.check_and_complete_idle_sessions(idle_seconds=600)
            except Exception as exc:
                logger.debug("Idle session check note: %s", exc)

    def ensure_running(self) -> Dict[str, Any]:
        if is_port_listening(self.port):
            lan_ip = get_lan_ip()
            return {
                "ok": True,
                "port": self.port,
                "localUrl": f"http://127.0.0.1:{self.port}",
                "lanUrl": f"http://{lan_ip}:{self.port}",
            }

        handler_cls = type(
            "BoundQuickExpenseRequestHandler",
            (QuickExpenseRequestHandler,),
            {
                "service": self.service,
                "template_dir": _resolve_template_dir(),
                "on_data_changed": staticmethod(self.on_data_changed) if self.on_data_changed else None,
            },
        )
        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), handler_cls)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="CSPMQuickExpenseServer",
            daemon=True,
        )
        self._thread.start()

        if self._idle_thread is None or not self._idle_thread.is_alive():
            self._idle_thread = threading.Thread(
                target=self._run_idle_session_checker,
                name="CSPMQuickExpenseIdleSessionWatcher",
                daemon=True,
            )
            self._idle_thread.start()

        lan_ip = get_lan_ip()
        return {
            "ok": True,
            "port": self.port,
            "localUrl": f"http://127.0.0.1:{self.port}",
            "lanUrl": f"http://{lan_ip}:{self.port}",
        }

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None


def open_standalone_dialog_window(url: str) -> bool:
    """Launch the Quick Expense UI in a standalone native frameless/app window
    (compiled Rust cspm-quick-expense binary if present, else Edge/Chrome --app mode
    on Windows/Linux/macOS, or default browser fallback)
    strictly using CREATE_NO_WINDOW on Windows per Rule 12."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    paths = AppPaths(root=AppPaths.project_root())
    rust_bin_name = "cspm-quick-expense.exe" if os.name == "nt" else "cspm-quick-expense"
    rust_candidates = [
        paths.root / "src" / "rust" / "cspm_quick_expense" / "target" / "release" / rust_bin_name,
        Path(sys.executable).resolve().parent / rust_bin_name,
        paths.root / rust_bin_name,
    ]
    for rust_exe in rust_candidates:
        if rust_exe.exists():
            try:
                env = os.environ.copy()
                env["CSPM_QUICK_EXPENSE_URL"] = url
                subprocess.Popen(
                    [str(rust_exe)],
                    env=env,
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                continue

    if os.name == "nt":
        browser_candidates = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for exe in browser_candidates:
            if exe.exists():
                try:
                    subprocess.Popen(
                        [
                            str(exe),
                            f"--app={url}",
                            "--window-size=820,860",
                        ],
                        creationflags=creationflags,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                except Exception:
                    continue
    elif sys.platform.startswith("linux"):
        for bin_name in ("google-chrome", "chromium-browser", "chromium", "microsoft-edge"):
            try:
                subprocess.Popen(
                    [bin_name, f"--app={url}", "--window-size=820,860"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                continue
    elif sys.platform == "darwin":
        chrome_mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_mac.exists():
            try:
                subprocess.Popen(
                    [str(chrome_mac), f"--app={url}", "--window-size=820,860"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass

    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="CSPM Quick Expense Mini-App Server & Launcher")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open-window", action="store_true", help="Open standalone dialog window")
    parser.add_argument("--user", type=str, default="", help="Optional initial user (deborah or cory)")
    parser.add_argument("--cli-action", type=str, default="", help="Run single JSON CLI command for Rust bridge")
    parser.add_argument("--payload-json", type=str, default="{}", help="JSON payload for --cli-action")
    args = parser.parse_args()

    service = QuickExpenseService()

    if args.cli_action:
        req = json.loads(args.payload_json or "{}")
        uid = str(req.get("userId") or args.user or "deborah")
        action = args.cli_action.lower()
        if action == "login":
            out = service.authenticate(str(req.get("username") or uid), str(req.get("pin") or ""))
        elif action == "bootstrap":
            out = service.get_bootstrap_data(user_id=uid)
        elif action == "entries":
            out = {
                "ok": True,
                "entries": service.list_entries(
                    user_id=uid,
                    period=str(req.get("period") or "today"),
                    date_from=str(req.get("dateFrom") or ""),
                    date_to=str(req.get("dateTo") or ""),
                    stream_id=str(req.get("streamId") or ""),
                ),
            }
        elif action == "report":
            out = service.build_report(
                user_id=uid,
                period=str(req.get("period") or "today"),
                date_from=str(req.get("dateFrom") or ""),
                date_to=str(req.get("dateTo") or ""),
                stream_id=str(req.get("streamId") or "ALL"),
            )
        elif action == "save":
            out = service.save_entry(user_id=uid, payload=req.get("payload") or req)
        elif action == "delete":
            out = service.delete_entry(user_id=uid, transaction_id=str(req.get("transactionId") or ""))
        else:
            out = {"ok": False, "message": f"Unknown cli-action: {action}"}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    try:
        service.get_bootstrap_data("deborah")
    except Exception:
        pass
    daemon = QuickExpenseServerDaemon(service=service, port=args.port)
    info = daemon.ensure_running()
    url = info["localUrl"]
    if args.user:
        url = f"{url}/?user={args.user}"

    if args.open_window:
        open_standalone_dialog_window(url)

    print(
        f"CSPM Quick Expense Server running:\n"
        f"  Local Desktop URL : {info['localUrl']}\n"
        f"  iPhone/Chromebook : {info['lanUrl']}"
    )
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        daemon.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
