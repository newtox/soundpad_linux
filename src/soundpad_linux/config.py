import json
import os
import shutil
from pathlib import Path

from .constants import APP_ID, DEFAULT_SINK
from .spl import stem_of
from .util import to_int

_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
CONFIG_DIR = _CONFIG_HOME / APP_ID
CONFIG_FILE = CONFIG_DIR / "config.json"
LEGACY_CONFIG_FILE = _CONFIG_HOME / "klangpad" / "config.json"

DEFAULT_SETTINGS = {
    "mic": None,
    "monitor_sink": DEFAULT_SINK,
    "monitor_enabled": True,
    "vol_others": 80,
    "vol_self": 60,
    "overlap": False,
    "tray": False,
    "language": "en",
    "theme": "dark",
    "last_dir": str(Path.home()),
}


def _migrate_legacy():
    if not CONFIG_FILE.exists() and LEGACY_CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)


def _normalize_sound(raw):
    return {
        "id": raw.get("id") if isinstance(raw.get("id"), int) else None,
        "title": raw.get("title") or stem_of(raw["path"]),
        "path": raw["path"],
        "orig": raw.get("orig") or raw["path"],
        "category": raw.get("category") or "",
        "duration": raw.get("duration"),
        "plays": to_int(raw.get("plays")),
    }


def _assign_ids(sounds):
    seen = set()
    for s in sounds:
        if s["id"] is None or s["id"] in seen:
            s["id"] = None
        else:
            seen.add(s["id"])
    next_id = max(seen, default=0) + 1
    for s in sounds:
        if s["id"] is None:
            s["id"] = next_id
            next_id += 1


def load_config():
    try:
        _migrate_legacy()
        data = json.loads(CONFIG_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    settings = dict(DEFAULT_SETTINGS)
    settings.update(data.get("settings") or {})
    sounds = [
        _normalize_sound(s)
        for s in data.get("sounds") or []
        if isinstance(s, dict) and s.get("path")
    ]
    _assign_ids(sounds)
    categories = {
        str(name): {k: v for k, v in meta.items() if k in ("color", "icon") and isinstance(v, str)}
        for name, meta in (data.get("categories") or {}).items()
        if isinstance(meta, dict) and name
    }
    return settings, sounds, categories


def load_settings():
    return load_config()[0]


def save_config(settings, sounds, categories):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    payload = {"settings": settings, "categories": categories, "sounds": sounds}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
    tmp.replace(CONFIG_FILE)
