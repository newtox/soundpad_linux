import json
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locales"
DEFAULT_LANGUAGE = "en"

_catalog = {}
_language = DEFAULT_LANGUAGE


def available_languages():
    languages = {DEFAULT_LANGUAGE: "English"}
    for f in sorted(LOCALE_DIR.glob("*.json")):
        try:
            languages[f.stem] = json.loads(f.read_text("utf-8")).get("_language_name", f.stem)
        except (OSError, ValueError):
            continue
    return languages


def load_catalog(code):
    return json.loads((LOCALE_DIR / f"{code}.json").read_text("utf-8"))


def set_language(code):
    global _catalog, _language
    _catalog = {}
    _language = DEFAULT_LANGUAGE
    if code and code != DEFAULT_LANGUAGE:
        try:
            _catalog = load_catalog(code)
            _language = code
        except (OSError, ValueError):
            pass


def current_language():
    return _language


def tr(text, **kwargs):
    translated = _catalog.get(text) or text
    return translated.format(**kwargs) if kwargs else translated
