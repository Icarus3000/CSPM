from __future__ import annotations

import json
from typing import Dict, List, Any

from services.paths import AppPaths


DEFAULT_LISTS: Dict[str, List[str]] = {
    "clients": [],
    "matters": [],
    "parents": []
}


class ListsService:
    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.path = self.paths.state_dir() / "lists.json"

    def load(self) -> Dict[str, List[str]]:
        if not self.path.exists():
            return dict(DEFAULT_LISTS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return dict(DEFAULT_LISTS)

        out: Dict[str, List[str]] = {}
        for k in ("clients", "matters", "parents"):
            v = raw.get(k, [])
            if not isinstance(v, list):
                v = []
            out[k] = [str(x).strip() for x in v if str(x).strip() != ""]
        for k in ("clients", "matters", "parents"):
            out.setdefault(k, [])
        return out

    def save(self, lists: Dict[str, Any]) -> None:
        self.paths.state_dir().mkdir(parents=True, exist_ok=True)
        payload: Dict[str, List[str]] = {}
        for k in ("clients", "matters", "parents"):
            v = lists.get(k, [])
            if not isinstance(v, list):
                v = []
            cleaned: List[str] = []
            for x in v:
                s = str(x).strip()
                if s and s not in cleaned:
                    cleaned.append(s)
            payload[k] = cleaned
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_value(self, list_name: str, value: str) -> Dict[str, List[str]]:
        value = (value or "").strip()
        lists = self.load()
        if value == "":
            return lists
        if list_name not in lists:
            return lists
        if value not in lists[list_name]:
            lists[list_name].append(value)
            self.save(lists)
        return lists
