from pathlib import Path

import pytest

from soundpad_linux import desktop_entry


@pytest.fixture(autouse=True)
def data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


def test_render_quotes_paths_with_spaces():
    text = desktop_entry.render("/home/justin/My Apps/Soundpad_Linux.AppImage")
    assert 'Exec="/home/justin/My Apps/Soundpad_Linux.AppImage"' in text
    assert "Icon=soundpad_linux" in text


def test_render_escapes_special_characters():
    assert desktop_entry.quote_exec('/a/"b"/$c') == '"/a/\\"b\\"/\\$c"'


def test_install_and_remove(data_home, tmp_path):
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")
    entry = desktop_entry.install("/opt/app.AppImage", icon)
    assert entry == data_home / "applications" / "soundpad_linux.desktop"
    assert Path(data_home / "icons/hicolor/256x256/apps/soundpad_linux.png").read_bytes() == b"png"
    assert desktop_entry.is_installed("/opt/app.AppImage")
    assert not desktop_entry.is_installed("/other/app.AppImage")
    desktop_entry.remove()
    assert not entry.exists()
    assert not desktop_entry.is_installed("/opt/app.AppImage")
