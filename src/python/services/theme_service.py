from __future__ import annotations

import json
from typing import Dict, Any, List

from services.paths import AppPaths
from services.theme_contrast import sanitize_theme_map


class ThemeService:
    def __init__(self, paths: AppPaths):
        self.paths = paths
        self._themes = self._load_themes()
        self._name = self._load_pref_name()

        if self._name not in self._themes:
            self._name = next(iter(self._themes.keys()))

    def _read_json_file(self, path):
        """
        Read JSON in a BOM-safe way.
        - utf-8-sig strips BOM if present
        """
        if not path.exists():
            raise RuntimeError(f"Missing required JSON file: {path}")

        try:
            raw = path.read_text(encoding="utf-8-sig")
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON: {path} ({e})")

    def _load_themes(self) -> Dict[str, Dict[str, Any]]:
        p = self.paths.themes_json_path()
        data = self._read_json_file(p)

        if not isinstance(data, dict) or "themes" not in data:
            raise RuntimeError('themes.json must be shaped like: {"themes": {...}}')

        themes = data["themes"]
        if not isinstance(themes, dict) or not themes:
            raise RuntimeError("themes.json contains no themes.")
        return sanitize_theme_map(themes)

    def _load_pref_name(self) -> str:
        prefs = self.paths.prefs_path()
        if not prefs.exists():
            return next(iter(self._themes.keys()))

        try:
            data = json.loads(prefs.read_text(encoding="utf-8-sig"))
        except Exception:
            return next(iter(self._themes.keys()))

        name = data.get("theme")
        if isinstance(name, str):
            return name
        return next(iter(self._themes.keys()))

    def theme_names(self) -> List[str]:
        return list(self._themes.keys())

    def current_name(self) -> str:
        return self._name

    def current_theme(self) -> Dict[str, Any]:
        return {"name": self._name, **self._themes[self._name]}

    def set_theme(self, name: str) -> None:
        if name not in self._themes:
            raise ValueError("Unknown theme")
        self._name = name
        self._save_pref()

    def _save_pref(self) -> None:
        self.paths.state_dir().mkdir(parents=True, exist_ok=True)
        payload = {"theme": self._name}
        self.paths.prefs_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
