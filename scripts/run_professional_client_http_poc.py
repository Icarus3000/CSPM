from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SRC = REPO_ROOT / "src" / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from repositories.excel_repo import ExcelRepo
from services.paths import AppPaths
from services.professional_client_loopback_host import ProfessionalClientLoopbackHost
from services.professional_client_service import (
    CLIENT_DIRECTORY_QUERY,
    CLIENT_PROFILE_QUERY,
    OPEN_CLIENT_PROFILE_ACTION,
    ProfessionalClientService,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _envelope(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "requestId": f"poc-{uuid4().hex}",
        "action": action,
        "payload": payload,
        "actor": "professional-http-poc",
        "timestampUtc": _utc_now(),
    }


def _post_json(
    *,
    url: str,
    session_token: str,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    request = Request(
        url=url,
        method="POST",
        data=json.dumps(envelope).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


def run_proof(project_root: Path) -> dict[str, Any]:
    repo = ExcelRepo(AppPaths(project_root))
    service = ProfessionalClientService(repo)

    with ProfessionalClientLoopbackHost(service) as host:
        info = host.info
        if info is None:
            raise RuntimeError("Professional client loopback host did not start.")

        directory_response = _post_json(
            url=info.base_url + info.query_path,
            session_token=host.session_token,
            envelope=_envelope(CLIENT_DIRECTORY_QUERY, {"activeOnly": False, "query": ""}),
        )
        if not directory_response.get("ok"):
            raise RuntimeError("Client Directory request failed through the loopback host.")

        rows = list((directory_response.get("payload") or {}).get("rows") or [])
        if not rows:
            raise RuntimeError("The active workbook has no client rows for the HTTP proof.")

        selected = dict(rows[0])
        client_key = str(selected.get("clientId") or selected.get("clientName") or "").strip()
        if not client_key:
            raise RuntimeError("The first Client Directory row has no stable lookup key.")

        profile_response = _post_json(
            url=info.base_url + info.query_path,
            session_token=host.session_token,
            envelope=_envelope(CLIENT_PROFILE_QUERY, {"clientId": client_key}),
        )
        if not profile_response.get("ok"):
            raise RuntimeError("Client Profile query failed through the loopback host.")

        open_response = _post_json(
            url=info.base_url + info.action_path,
            session_token=host.session_token,
            envelope=_envelope(OPEN_CLIENT_PROFILE_ACTION, {"clientId": client_key}),
        )
        if not open_response.get("ok"):
            raise RuntimeError("Open Client Profile action failed through the loopback host.")

        profile = dict((profile_response.get("payload") or {}).get("profile") or {})
        tab = dict((open_response.get("payload") or {}).get("tab") or {})
        events = service.events.drain_events()

        return {
            "status": "PASS",
            "transport": info.to_dict(),
            "directoryCount": len(rows),
            "profileLoaded": bool(profile.get("client")),
            "option3ClientIdentityPreserved": (
                tab.get("entityType") == "client"
                and bool(tab.get("entityId"))
                and tab.get("route") == "/clients/profile"
            ),
            "eventNames": [str(event.get("name") or "") for event in events],
            "webSocketEventsImplemented": False,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the CSPM Professional-client HTTP proof against the active workbook."
    )
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="CSPM project root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_proof(Path(args.project_root).resolve())

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("CSPM Professional-client HTTP proof")
        print(f"Status: {result['status']}")
        print(f"Directory rows: {result['directoryCount']}")
        print(f"Profile loaded: {result['profileLoaded']}")
        print(f"Option 3 client identity preserved: {result['option3ClientIdentityPreserved']}")
        print(f"Events published: {', '.join(result['eventNames'])}")
        print("WebSocket events: deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
