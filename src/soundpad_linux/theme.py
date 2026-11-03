from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

THEMES = {
    "dark": {
        "window": "#17181f",
        "base": "#1f2029",
        "alt": "#242531",
        "text": "#ececf3",
        "muted": "#9c9db0",
        "border": "#33354a",
        "button": "#272838",
        "hover": "#30324a",
        "accent": "#8b6cff",
        "accent2": "#22c3ff",
    },
    "light": {
        "window": "#f3f4fb",
        "base": "#ffffff",
        "alt": "#f7f7fd",
        "text": "#1c1d29",
        "muted": "#6b6d80",
        "border": "#dcdeec",
        "button": "#ffffff",
        "hover": "#eceaff",
        "accent": "#6a4cff",
        "accent2": "#0aa7e6",
    },
}

DANGER = "#ef4b5c"
MISSING = "#ef4b5c"

STYLESHEET = Template("""
QMainWindow, QDialog { background: $window; }
QToolBar { background: $window; border: none; padding: 6px 8px; spacing: 6px; }
QToolButton { background: $button; color: $text; border: 1px solid $border; border-radius: 9px;
    padding: 6px 12px; font-weight: 600; }
QToolButton:hover { border-color: $accent; background: $hover; }
QToolButton:pressed { background: $accent; color: white; }
QPushButton { background: $button; color: $text; border: 1px solid $border; border-radius: 9px; padding: 6px 14px; }
QPushButton:hover { border-color: $accent; background: $hover; }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2);
    color: white; border: none; font-weight: 700; padding: 7px 18px; }
QPushButton#danger { background: $danger; color: white; border: none; font-weight: 700; padding: 7px 18px; }
QPushButton#swatch { border: 2px solid transparent; border-radius: 13px; padding: 0; }
QPushButton#swatch:checked { border: 3px solid $text; }
QPushButton#emoji { background: $base; border: 1px solid $border; border-radius: 8px; padding: 0; font-size: 18px; }
QPushButton#emoji:checked { background: $hover; border: 2px solid $accent; }
QLineEdit, QComboBox { background: $base; color: $text; border: 1px solid $border; border-radius: 9px;
    padding: 6px 10px; selection-background-color: $accent; }
QLineEdit:focus, QComboBox:focus { border-color: $accent; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: $base; color: $text; border: 1px solid $border;
    selection-background-color: $accent; selection-color: white; }
QTableView { background: $base; alternate-background-color: $alt; color: $text; border: 1px solid $border;
    border-radius: 12px; gridline-color: transparent; selection-background-color: $selection;
    selection-color: $text; outline: 0; }
QTableView::item { padding: 4px 6px; border: none; }
QHeaderView { background: transparent; }
QHeaderView::section { background: $base; color: $muted; border: none; border-bottom: 2px solid $accent;
    padding: 7px 8px; font-weight: 700; }
QListWidget { background: $base; color: $text; border: 1px solid $border; border-radius: 12px;
    padding: 4px; outline: 0; }
QGroupBox { border: 1px solid $border; border-radius: 12px; margin-top: 16px;
    padding: 12px 10px 10px 10px; color: $text; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: $accent; font-weight: 700; }
QProgressBar { background: $base; border: 1px solid $border; border-radius: 11px; text-align: center; color: $text;
    min-height: 24px; font-weight: 600; }
QProgressBar::chunk { border-radius: 10px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QSlider::groove:horizontal { height: 6px; background: $border; border-radius: 3px; }
QSlider::sub-page:horizontal { border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }
QSlider::handle:horizontal { background: white; border: 3px solid $accent; width: 12px; height: 12px;
    margin: -6px 0; border-radius: 9px; }
QCheckBox { color: $text; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid $border; background: $base; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
QLabel { color: $text; }
QLabel#muted { color: $muted; }
QStatusBar { background: $window; color: $muted; }
QStatusBar QLabel { color: $muted; }
QMenuBar { background: $window; color: $text; padding: 2px; }
QMenuBar::item { padding: 5px 10px; border-radius: 6px; }
QMenuBar::item:selected { background: $hover; }
QMenu { background: $base; color: $text; border: 1px solid $border; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 6px; }
QMenu::item:selected { background: $accent; color: white; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }
QSplitter::handle { background: transparent; width: 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    width: 0; height: 0; background: none; }
QToolTip { background: $base; color: $text; border: 1px solid $accent; border-radius: 6px; padding: 4px; }
""")

_original = {}


def _rgba(hex_color, alpha):
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _palette(colors):
    p = QPalette()
    roles = {
        QPalette.Window: colors["window"],
        QPalette.WindowText: colors["text"],
        QPalette.Base: colors["base"],
        QPalette.AlternateBase: colors["alt"],
        QPalette.Text: colors["text"],
        QPalette.Button: colors["button"],
        QPalette.ButtonText: colors["text"],
        QPalette.Highlight: colors["accent"],
        QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: colors["base"],
        QPalette.ToolTipText: colors["text"],
        QPalette.PlaceholderText: colors["muted"],
        QPalette.Link: colors["accent"],
        QPalette.Mid: colors["border"],
    }
    for role, value in roles.items():
        p.setColor(role, QColor(value))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(colors["muted"]))
    return p


def colors_for(name):
    return THEMES.get(name)


def apply_theme(name):
    app = QApplication.instance()
    if not _original:
        _original["style"] = app.style().name()
        _original["palette"] = QPalette(app.palette())
    colors = THEMES.get(name)
    if colors is None:
        app.setStyleSheet("")
        app.setStyle(QStyleFactory.create(_original["style"]))
        app.setPalette(_original["palette"])
        return
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_palette(colors))
    app.setStyleSheet(STYLESHEET.substitute(colors, danger=DANGER, selection=_rgba(colors["accent"], 90)))
