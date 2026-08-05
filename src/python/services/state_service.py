from __future__ import annotations

import json
from typing import Dict, Any

from services.paths import AppPaths


class StateService:
    def __init__(self, paths: AppPaths):
        self.paths = paths

    def load_json(self, path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save_json(self, path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_last_entry(self) -> Dict[str, Any]:
        return self.load_json(self.paths.last_entry_path(), {})

    def save_last_entry(self, payload: Dict[str, Any]) -> None:
        self.save_json(self.paths.last_entry_path(), payload)

    def load_prefs(self) -> Dict[str, Any]:
        return self.load_json(self.paths.prefs_path(), {})

    def save_prefs(self, payload: Dict[str, Any]) -> None:
        self.save_json(self.paths.prefs_path(), payload)

    def load_lists(self) -> Dict[str, Any]:
        p = self.paths.state_dir() / "lists.json"
        return self.load_json(p, {})
