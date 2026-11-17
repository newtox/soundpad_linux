import os
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .constants import APP_ID, APP_NAME


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def entry_path():
    return data_home() / "applications" / f"{APP_ID}.desktop"


def icon_path():
    return data_home() / "icons" / "hicolor" / "256x256" / "apps" / f"{APP_ID}.png"


def quote_exec(path):
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return f'"{escaped}"'


def render(exec_path):
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_NAME}",
        "GenericName=Soundboard",
        "Comment=Soundboard with a virtual microphone",
        "Comment[de]=Soundboard mit virtuellem Mikrofon",
        f"Exec={quote_exec(exec_path)}",
        f"Icon={APP_ID}",
        "Terminal=false",
        "Categories=AudioVideo;Audio;",
        "Keywords=soundpad;soundboard;",
        f"StartupWMClass={APP_ID}",
        f"X-AppImage-Version={__version__}",
        "",
    ])


def is_installed(exec_path):
    try:
        return quote_exec(exec_path) in entry_path().read_text("utf-8")
    except OSError:
        return False


def _refresh():
    tool = shutil.which("update-desktop-database")
    if tool:
        subprocess.run([tool, str(entry_path().parent)], capture_output=True, timeout=10)


def install(exec_path, icon_source):
    icon_path().parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(icon_source, icon_path())
    entry_path().parent.mkdir(parents=True, exist_ok=True)
    entry_path().write_text(render(exec_path), "utf-8")
    _refresh()
    return entry_path()


def remove():
    for path in (entry_path(), icon_path()):
        path.unlink(missing_ok=True)
    _refresh()
