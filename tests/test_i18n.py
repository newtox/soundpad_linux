import ast
import re
from pathlib import Path

import pytest

from soundpad_linux import i18n

SRC = Path(__file__).parent.parent / "src" / "soundpad_linux"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def source_strings():
    keys = set()
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text("utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args:
                arg = node.args[0]
                assert isinstance(arg, ast.Constant), f"tr() needs a string literal in {f.name}: {ast.unparse(node)}"
                keys.add(arg.value)
    return keys


LANGUAGES = [code for code in i18n.available_languages() if code != i18n.DEFAULT_LANGUAGE]


def test_has_german():
    assert "de" in LANGUAGES


@pytest.mark.parametrize("code", LANGUAGES)
def test_catalog_is_complete(code):
    catalog = i18n.load_catalog(code)
    keys = source_strings()
    missing = sorted(keys - catalog.keys())
    unused = sorted(k for k in catalog.keys() - keys if not k.startswith("_"))
    assert not missing, f"missing translations: {missing}"
    assert not unused, f"unused translations: {unused}"


@pytest.mark.parametrize("code", LANGUAGES)
def test_placeholders_match(code):
    for key, value in i18n.load_catalog(code).items():
        if not key.startswith("_"):
            assert set(PLACEHOLDER.findall(key)) == set(PLACEHOLDER.findall(value)), key


def test_tr_switches_language():
    try:
        i18n.set_language("de")
        assert i18n.tr("Stop") == "Stopp"
        assert i18n.tr("{n} sounds imported.", n=3) == "3 Sounds importiert."
        i18n.set_language("en")
        assert i18n.tr("Stop") == "Stop"
        i18n.set_language("xx")
        assert i18n.current_language() == "en"
    finally:
        i18n.set_language("en")
