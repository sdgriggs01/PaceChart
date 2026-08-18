"""Persisted pace-selection templates.

Design.md: "save into app data different templates of paces." A template
is just a named set of enabled (zone, distance) pace keys, stored as one
JSON file in the user's app data directory. Pure I/O module — no
Tkinter, no AppState dependency (the GUI reads/writes AppState.enabled_paces
directly around calls into this module).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pacechart.app_state import PaceKey


def default_storage_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home())))
    return base / "PaceChart" / "templates.json"


def _load_all(storage_path: Path) -> dict[str, list[PaceKey]]:
    if not storage_path.exists():
        return {}
    raw = json.loads(storage_path.read_text(encoding="utf-8"))
    return {name: [(zone, dist) for zone, dist in keys] for name, keys in raw.items()}


def _save_all(storage_path: Path, templates: dict[str, list[PaceKey]]) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {name: [list(key) for key in keys] for name, keys in templates.items()}
    storage_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def list_templates(storage_path: Path | None = None) -> list[str]:
    storage_path = storage_path or default_storage_path()
    return sorted(_load_all(storage_path).keys())


def save_template(name: str, enabled_paces: set[PaceKey], storage_path: Path | None = None) -> None:
    if not name.strip():
        raise ValueError("Template name must not be empty")
    storage_path = storage_path or default_storage_path()
    templates = _load_all(storage_path)
    templates[name] = sorted(enabled_paces)
    _save_all(storage_path, templates)


def load_template(name: str, storage_path: Path | None = None) -> set[PaceKey]:
    storage_path = storage_path or default_storage_path()
    templates = _load_all(storage_path)
    if name not in templates:
        raise KeyError(f"No such template: {name!r}")
    return set(templates[name])


def delete_template(name: str, storage_path: Path | None = None) -> None:
    storage_path = storage_path or default_storage_path()
    templates = _load_all(storage_path)
    if name not in templates:
        raise KeyError(f"No such template: {name!r}")
    del templates[name]
    _save_all(storage_path, templates)
