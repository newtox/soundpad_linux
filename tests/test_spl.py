from pathlib import Path

import pytest

from soundpad_linux.spl import is_windows_path, parse_spl, resolve_missing, url_to_path

FIXTURE = Path(__file__).parent / "fixtures" / "example.spl"


@pytest.fixture
def sounds():
    return parse_spl(FIXTURE)


def test_parses_all_sounds(sounds):
    assert [s["title"] for s in sounds] == ["Airhorn", "bruh", "Fehlt & weg"]


def test_reads_metadata(sounds):
    assert sounds[0]["duration"] == 2.0
    assert sounds[0]["plays"] == 12
    assert sounds[2]["duration"] == 65.0


def test_categories_skip_all_sounds(sounds):
    assert [s["category"] for s in sounds] == ["Memes", "Memes", ""]


def test_keeps_original_windows_path(sounds):
    assert is_windows_path(sounds[0]["orig"])
    assert sounds[0]["orig"].endswith("Airhorn.mp3")


def test_resolves_by_filename_case_insensitive(sounds, tmp_path):
    (tmp_path / "Memes").mkdir()
    (tmp_path / "Memes" / "airhorn.mp3").write_bytes(b"")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "airhorn.mp3").write_bytes(b"")
    (tmp_path / "bruh.wav").write_bytes(b"")

    fixed = resolve_missing(sounds, [tmp_path])

    assert fixed == 2
    assert sounds[0]["path"] == str(tmp_path / "Memes" / "airhorn.mp3")
    assert sounds[1]["path"] == str(tmp_path / "bruh.wav")
    assert sounds[2]["path"] == sounds[2]["orig"]


def test_broken_xml_falls_back_to_regex(tmp_path):
    spl = tmp_path / "broken.spl"
    spl.write_text('<Soundlist><Sound url="C:\\a\\b.mp3" title="B" duration="0:03"><Sound url="/x/c.ogg"/>')
    titles = [s["title"] for s in parse_spl(spl)]
    assert titles == ["B", "c"]


def test_utf16_file(tmp_path):
    spl = tmp_path / "utf16.spl"
    xml = '<?xml version="1.0" encoding="UTF-16"?><Soundlist><Sound url="C:\\ä.mp3"/></Soundlist>'
    spl.write_bytes(xml.encode("utf-16"))
    assert parse_spl(spl)[0]["title"] == "ä"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("file:///C:/Sounds/a%20b.mp3", "C:/Sounds/a b.mp3"),
        ("file:///home/justin/x.mp3", "/home/justin/x.mp3"),
        ("C:\\Sounds\\a.mp3", "C:\\Sounds\\a.mp3"),
    ],
)
def test_url_to_path(url, expected):
    assert url_to_path(url) == expected
