import argparse
import signal
import sys

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from . import __version__
from .config import load_settings
from .constants import APP_ID, APP_NAME
from .i18n import set_language, tr
from .ipc import send_command


def build_parser():
    parser = argparse.ArgumentParser(
        prog=APP_ID,
        description=tr("Soundboard for Linux with a virtual microphone. Starts the GUI when called without arguments."),
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--play", type=int, metavar="NR", help=tr("play the sound with this number"))
    group.add_argument("--play-title", metavar="TEXT", help=tr("play a sound by its title"))
    group.add_argument("--random", action="store_true", help=tr("play a random sound"))
    group.add_argument("--stop", action="store_true", help=tr("stop all sounds"))
    return parser


def command_from_args(args):
    if args.play is not None:
        return {"cmd": "play", "id": args.play}
    if args.play_title:
        return {"cmd": "play_title", "title": args.play_title}
    if args.random:
        return {"cmd": "random"}
    if args.stop:
        return {"cmd": "stop"}
    return None


def run_remote(cmd):
    _app = QCoreApplication(sys.argv)
    if send_command(cmd):
        return 0
    print(tr("{app} is not running.", app=APP_NAME), file=sys.stderr)
    return 1


def run_gui():
    from .ui import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setQuitOnLastWindowClosed(False)
    if send_command({"cmd": "show"}):
        return 0

    window = MainWindow()
    window.show()
    app.aboutToQuit.connect(window.cleanup)
    signal.signal(signal.SIGINT, lambda *_: window.quit_app())
    signal.signal(signal.SIGTERM, lambda *_: window.quit_app())
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(300)
    return app.exec()


def main():
    if not sys.platform.startswith("linux"):
        print(tr("{app} only runs on Linux.", app=APP_NAME), file=sys.stderr)
        return 1
    set_language(load_settings().get("language"))
    args, _qt_args = build_parser().parse_known_args()
    cmd = command_from_args(args)
    return run_remote(cmd) if cmd else run_gui()
