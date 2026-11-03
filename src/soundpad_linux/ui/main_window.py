import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..audio import AudioRouter
from ..categories import Categories
from ..config import load_config, save_config
from ..constants import (
    APP_ID,
    APP_NAME,
    AUDIO_EXT,
    DEFAULT_SINK,
    EASYEFFECTS_SOURCE,
    MIX_SINK,
    VIRTUAL_MIC_LABEL,
)
from ..i18n import available_languages, tr
from ..ipc import CommandServer
from ..models import CATEGORY_COLUMN, FilterProxy, SoundModel
from ..player import Player, Prober
from ..spl import is_windows_path, parse_spl, resolve_missing
from ..theme import DANGER, apply_theme, colors_for
from ..util import fmt_duration
from .category_dialog import CategoryDialog
from .delegates import CategoryChipDelegate, CategoryListDelegate
from .widgets import (
    ALL,
    COLOR_ROLE,
    COUNT_ROLE,
    ICON_ROLE,
    VALUE_ROLE,
    CategoryList,
    SoundTable,
    VolumeSlider,
    app_icon,
)

REPO_URL = "https://github.com/newtox/soundpad_linux"


def audio_filter():
    patterns = " ".join(f"*{e}" for e in sorted(AUDIO_EXT))
    return f"{tr('Audio files')} ({patterns});;{tr('All files')} (*)"


def cli_command():
    if shutil.which(APP_ID):
        return APP_ID
    return f"{sys.executable} -m soundpad_linux"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings, self.sounds, category_data = load_config()
        self.categories = Categories(category_data)
        apply_theme(self.settings["theme"])

        self.router = AudioRouter()
        self.player = Player()
        self.prober = Prober()
        self.save_timer = QTimer(self, singleShot=True, interval=400)
        self.save_timer.timeout.connect(self._save_now)
        self.cleaned_up = False
        self.quitting = False

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1060, 720)
        self.setAcceptDrops(True)

        self.model = SoundModel(self.sounds)
        self.model.edited.connect(self._on_edited)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)

        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self._build_tray()
        self._build_shortcuts()

        self.server = CommandServer(self)
        self.server.received.connect(self.handle_command)
        self.player.changed.connect(self._on_player_changed)
        self.prober.probed.connect(self._on_probed)

        self._init_audio()
        self._refresh_categories()
        self._probe_unknown()

    def _action(self, text, slot, shortcut=None, menu=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if menu is not None:
            menu.addAction(a)
        return a

    def _build_menu(self):
        bar = self.menuBar()

        m = bar.addMenu(tr("&File"))
        self._action(tr("Add sounds …"), self.add_files_dialog, "Ctrl+O", m)
        self._action(tr("Add folder …"), self.add_folder_dialog, "Ctrl+Shift+O", m)
        self._action(tr("Import Soundpad list (.spl) …"), self.import_spl_dialog, "Ctrl+I", m)
        self._action(tr("Find missing files …"), self.find_missing_dialog, None, m)
        m.addSeparator()
        self._action(tr("New category …"), self.new_category, "Ctrl+N", m)
        m.addSeparator()
        self._action(tr("Quit"), self.quit_app, "Ctrl+Q", m)

        m = bar.addMenu(tr("&Playback"))
        self._action(tr("Play selected"), self.play_selected, None, m)
        self._action(tr("Play random sound"), self.play_random, "Ctrl+R", m)
        self._action(tr("Stop all"), self.player.stop_all, None, m)

        m = bar.addMenu(tr("&View"))
        theme_menu = m.addMenu(tr("Theme"))
        group = QActionGroup(self)
        for key, label in (("dark", tr("Dark")), ("light", tr("Light")), ("system", tr("System"))):
            a = self._action(label, lambda _c=False, k=key: self.set_theme(k), None, theme_menu)
            a.setCheckable(True)
            a.setChecked(self.settings["theme"] == key)
            group.addAction(a)

        lang_menu = m.addMenu(tr("Language"))
        group = QActionGroup(self)
        for code, label in available_languages().items():
            a = self._action(label, lambda _c=False, c=code: self.set_language(c), None, lang_menu)
            a.setCheckable(True)
            a.setChecked(self.settings["language"] == code)
            group.addAction(a)

        m.addSeparator()
        self.tray_action = self._action(tr("Minimize to tray on close"), lambda v: self._set("tray", v), None, m)
        self.tray_action.setCheckable(True)
        self.tray_action.setChecked(bool(self.settings["tray"]))

        m = bar.addMenu(tr("&Help"))
        self._action(tr("Project on GitHub"), lambda: QDesktopServices.openUrl(QUrl(REPO_URL)), None, m)
        self._action(tr("About {app}", app=APP_NAME), self.show_about, None, m)

    def _build_toolbar(self):
        tb = QToolBar(tr("Toolbar"))
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        for text, slot in (
            ("➕  " + tr("Add sounds"), self.add_files_dialog),
            ("📁  " + tr("Add folder"), self.add_folder_dialog),
            ("📥  " + tr("Import .spl"), self.import_spl_dialog),
            ("🔍  " + tr("Find missing"), self.find_missing_dialog),
            ("🏷️  " + tr("New category"), self.new_category),
        ):
            tb.addAction(self._action(text, slot))
        tb.addSeparator()
        tb.addAction(self._action("🎲  " + tr("Random"), self.play_random))

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 4, 10, 6)
        root.setSpacing(8)
        root.addWidget(self._build_library(), 1)
        root.addLayout(self._build_now_playing())
        root.addWidget(self._build_audio_box())
        self.setCentralWidget(central)

        self.audio_status = QLabel()
        self.audio_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.statusBar().addPermanentWidget(self.audio_status, 1)

    def _build_library(self):
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        title = QLabel(tr("Categories"))
        title.setObjectName("muted")
        title.setStyleSheet("font-weight: 700; padding: 2px 4px;")
        ll.addWidget(title)
        self.cat_list = CategoryList()
        self.cat_list.setItemDelegate(CategoryListDelegate(self.cat_list))
        self.cat_list.setMinimumWidth(190)
        self.cat_list.currentItemChanged.connect(self._on_category_changed)
        self.cat_list.itemDoubleClicked.connect(lambda item: self.edit_category(item.data(VALUE_ROLE)))
        self.cat_list.soundsDropped.connect(self._on_sounds_dropped)
        self.cat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cat_list.customContextMenuRequested.connect(self._category_context_menu)
        ll.addWidget(self.cat_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎  " + tr("Search …  (Ctrl+F)"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.proxy.set_text)
        self.search.returnPressed.connect(self._play_first_visible)
        rl.addWidget(self.search)

        self.table = SoundTable()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(CATEGORY_COLUMN, CategoryChipDelegate(self.categories, self.table))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for col, width in ((0, 60), (2, 170), (3, 80), (4, 80)):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)
        self.table.doubleClicked.connect(lambda _i: self.play_selected())
        self.table.playRequested.connect(self.play_selected)
        self.table.deleteRequested.connect(self.remove_selected)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._sound_context_menu)
        rl.addWidget(self.table)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 840])
        return splitter

    def _build_now_playing(self):
        row = QHBoxLayout()
        play_btn = QPushButton("▶  " + tr("Play"))
        play_btn.setObjectName("primary")
        play_btn.clicked.connect(self.play_selected)
        row.addWidget(play_btn)
        stop_btn = QPushButton("■  " + tr("Stop"))
        stop_btn.setObjectName("danger")
        stop_btn.clicked.connect(self.player.stop_all)
        row.addWidget(stop_btn)
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat(tr("Ready"))
        self.progress.setValue(0)
        row.addWidget(self.progress, 1)
        return row

    def _build_audio_box(self):
        box = QGroupBox(tr("Audio"))
        g = QGridLayout(box)
        g.setHorizontalSpacing(12)

        g.addWidget(QLabel("🎤  " + tr("Microphone (mixed in):")), 0, 0)
        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumWidth(300)
        self.mic_combo.activated.connect(self._on_mic_selected)
        g.addWidget(self.mic_combo, 0, 1)
        refresh = QPushButton("🔄  " + tr("Reconnect"))
        refresh.setToolTip(tr("Refresh the device list and reconnect the microphone (e.g. after starting EasyEffects)"))
        refresh.clicked.connect(self._reconnect_audio)
        g.addWidget(refresh, 0, 2)

        self.monitor_check = QCheckBox("🎧  " + tr("Hear sounds myself on:"))
        self.monitor_check.setChecked(bool(self.settings["monitor_enabled"]))
        self.monitor_check.toggled.connect(self._on_monitor_toggled)
        g.addWidget(self.monitor_check, 1, 0)
        self.sink_combo = QComboBox()
        self.sink_combo.activated.connect(self._on_sink_selected)
        g.addWidget(self.sink_combo, 1, 1)
        self.overlap_check = QCheckBox(tr("Play multiple sounds at once"))
        self.overlap_check.setChecked(bool(self.settings["overlap"]))
        self.overlap_check.toggled.connect(lambda v: self._set("overlap", v))
        g.addWidget(self.overlap_check, 1, 2)

        self.vol_others = VolumeSlider(self.settings["vol_others"], lambda v: self._set("vol_others", v))
        self.vol_self = VolumeSlider(self.settings["vol_self"], lambda v: self._set("vol_self", v))
        g.addWidget(QLabel("📢  " + tr("Volume for others:")), 2, 0)
        g.addWidget(self.vol_others, 2, 1)
        g.addWidget(self.vol_others.label, 2, 2)
        g.addWidget(QLabel("🔈  " + tr("Volume for me:")), 3, 0)
        g.addWidget(self.vol_self, 3, 1)
        g.addWidget(self.vol_self.label, 3, 2)
        g.setColumnStretch(1, 1)
        return box

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        menu.addAction(tr("Show"), self._show_window)
        menu.addAction(tr("Stop"), self.player.stop_all)
        menu.addAction(tr("Play random sound"), self.play_random)
        menu.addSeparator()
        menu.addAction(tr("Quit"), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._toggle_window() if reason == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Esc"), self, activated=self.player.stop_all)
        QShortcut(QKeySequence.Find, self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))

    def set_theme(self, name):
        self._set("theme", name)
        apply_theme(name)
        self._update_audio_status()
        self.cat_list.viewport().update()
        self.table.viewport().update()

    def set_language(self, code):
        if code == self.settings["language"]:
            return
        self._set("language", code)
        answer = QMessageBox.question(
            self, APP_NAME, tr("The language will change after a restart. Restart now?"),
        )
        if answer == QMessageBox.Yes:
            self.restart_app()

    def restart_app(self):
        self.quitting = True
        self.cleanup()
        os.execv(sys.executable, [sys.executable, "-m", "soundpad_linux"])

    def show_about(self):
        QMessageBox.about(
            self, tr("About {app}", app=APP_NAME),
            f"<h3>{APP_NAME} {__version__}</h3>"
            f"<p>{tr('Soundboard for Linux with a virtual microphone and Soundpad list import.')}</p>"
            f'<p><a href="{REPO_URL}">{REPO_URL}</a></p>'
            f"<p>{tr('Unofficial project, not affiliated with Soundpad or Leppsoft.')}</p>",
        )

    def handle_command(self, cmd):
        c = cmd.get("cmd")
        if c == "play":
            s = self._by_id(cmd.get("id"))
            if s:
                self.play(s)
        elif c == "play_title":
            q = str(cmd.get("title", "")).lower().strip()
            matches = [s for s in self.sounds if s["title"].lower() == q] or [
                s for s in self.sounds if q and q in s["title"].lower()
            ]
            if matches:
                self.play(matches[0])
        elif c == "random":
            self.play_random()
        elif c == "stop":
            self.player.stop_all()
        elif c == "show":
            self._show_window()

    def _init_audio(self):
        missing = Player.missing_tools()
        if missing:
            QMessageBox.warning(
                self, APP_NAME,
                tr("The following programs are missing: {tools}", tools=", ".join(missing))
                + "\n\n" + tr("Install with:") + "\n  sudo dnf install ffmpeg pulseaudio-utils",
            )
        self.router.setup()
        self._fill_devices()
        mic = self.settings["mic"]
        if mic is None:
            mic = self._auto_mic()
            self.settings["mic"] = mic
            self._schedule_save()
            self.mic_combo.setCurrentIndex(max(self.mic_combo.findData(mic), 0))
        self.router.set_mic(mic)
        self._update_audio_status()

    def _auto_mic(self):
        names = [self.mic_combo.itemData(i) for i in range(self.mic_combo.count())]
        if EASYEFFECTS_SOURCE in names:
            return EASYEFFECTS_SOURCE
        return self.router.default_source() or ""

    def _fill_devices(self):
        has_pactl = self.router.available()

        mic = self.settings["mic"]
        self.mic_combo.clear()
        self.mic_combo.addItem(tr("No microphone (sounds only)"), "")
        sources = self.router.list_devices("sources") if has_pactl else []
        sources.sort(key=lambda d: (d[0] != EASYEFFECTS_SOURCE, d[0].endswith(".monitor"), d[1].lower()))
        for name, desc in sources:
            is_monitor = name.endswith(".monitor") and "monitor" not in desc.lower()
            self.mic_combo.addItem(f"{desc}  ({tr('Monitor')})" if is_monitor else desc, name)
        if mic and self.mic_combo.findData(mic) < 0:
            self.mic_combo.addItem(f"{mic}  ({tr('not available')})", mic)
        self.mic_combo.setCurrentIndex(max(self.mic_combo.findData(mic or ""), 0))

        sink = self.settings["monitor_sink"]
        self.sink_combo.clear()
        self.sink_combo.addItem(tr("Default output"), DEFAULT_SINK)
        for name, desc in (self.router.list_devices("sinks") if has_pactl else []):
            self.sink_combo.addItem(desc, name)
        if sink and self.sink_combo.findData(sink) < 0:
            self.sink_combo.addItem(f"{sink}  ({tr('not available')})", sink)
        self.sink_combo.setCurrentIndex(max(self.sink_combo.findData(sink), 0))
        self.sink_combo.setEnabled(self.monitor_check.isChecked())

    def _reconnect_audio(self):
        self.router.error = ""
        if not self.router.ready:
            self.router.setup()
        self._fill_devices()
        self.router.set_mic(self.settings["mic"])
        self._update_audio_status()

    def _update_audio_status(self):
        if self.router.ready and not self.router.error:
            mic_text = self.mic_combo.currentText() if self.settings["mic"] else tr("no microphone")
            self.audio_status.setText(
                "✔  " + tr(
                    "Virtual microphone active – select »{device}« as input in Discord or your game.  "
                    "Mix: {mic} + sounds",
                    device=VIRTUAL_MIC_LABEL, mic=mic_text,
                )
            )
            colors = colors_for(self.settings["theme"])
            self.audio_status.setStyleSheet(f"color: {colors['muted']};" if colors else "")
        else:
            self.audio_status.setText("⚠  " + (self.router.error or tr("Audio routing is not active")))
            self.audio_status.setStyleSheet(f"color: {DANGER};")

    def _on_mic_selected(self, _index):
        mic = self.mic_combo.currentData() or ""
        self._set("mic", mic)
        self.router.error = ""
        self.router.set_mic(mic)
        self._update_audio_status()

    def _on_sink_selected(self, _index):
        self._set("monitor_sink", self.sink_combo.currentData() or DEFAULT_SINK)

    def _on_monitor_toggled(self, value):
        self.sink_combo.setEnabled(value)
        self._set("monitor_enabled", value)

    def _set(self, key, value):
        self.settings[key] = value
        self._schedule_save()

    def _schedule_save(self):
        self.save_timer.start()

    def _save_now(self):
        try:
            save_config(self.settings, self.sounds, self.categories.data)
        except OSError as e:
            self.statusBar().showMessage(tr("Saving failed: {error}", error=e), 5000)

    def _on_edited(self):
        self._refresh_categories()
        self._schedule_save()

    def _by_id(self, sid):
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return None
        return next((s for s in self.sounds if s["id"] == sid), None)

    def _selected_sounds(self):
        rows = sorted({self.proxy.mapToSource(i).row() for i in self.table.selectionModel().selectedRows()})
        return [self.sounds[r] for r in rows]

    def _visible_sounds(self):
        return [
            self.sounds[self.proxy.mapToSource(self.proxy.index(r, 0)).row()]
            for r in range(self.proxy.rowCount())
        ]

    def _probe_unknown(self, sounds=None):
        sounds = self.sounds if sounds is None else sounds
        self.prober.run(
            (s["id"], s["path"])
            for s in sounds
            if not s.get("duration") and s["id"] not in self.model.missing
        )

    def play(self, sound, only_self=False):
        if not os.path.isfile(sound["path"]):
            self.statusBar().showMessage(tr("File not found: {path}", path=sound["path"]), 5000)
            return
        if Player.missing_tools():
            self.statusBar().showMessage(tr("ffmpeg/pacat are missing – cannot play sounds."), 5000)
            return
        targets = []
        if self.router.ready and not only_self:
            targets.append((MIX_SINK, self.settings["vol_others"] / 100))
        if self.settings["monitor_enabled"] or only_self:
            vol = self.settings["vol_self"] / 100 or (0.6 if only_self else 0)
            targets.append((self.settings["monitor_sink"] or DEFAULT_SINK, vol))
        if not self.player.play(sound, targets, self.settings["overlap"]):
            self.statusBar().showMessage(tr("No active output (volumes at 0 or routing disabled)."), 5000)
            return
        sound["plays"] = int(sound.get("plays", 0)) + 1
        self.model.update_row(self.model.row_of(sound["id"]))
        self._schedule_save()

    def play_selected(self):
        sel = self._selected_sounds()
        if not sel and self.table.currentIndex().isValid():
            sel = [self.sounds[self.proxy.mapToSource(self.table.currentIndex()).row()]]
        if sel:
            self.play(sel[0])

    def _play_first_visible(self):
        visible = self._visible_sounds()
        if visible:
            self.table.selectRow(0)
            self.play(visible[0])

    def play_random(self):
        pool = [s for s in self._visible_sounds() if s["id"] not in self.model.missing]
        if pool:
            self.play(random.choice(pool))

    def _on_player_changed(self):
        self.model.set_playing(self.player.playing_ids())
        if not self.player.active:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setFormat(tr("Ready"))
            return
        pb = self.player.active[-1]
        elapsed = time.monotonic() - pb.started
        extra = f"  (+{len(self.player.active) - 1})" if len(self.player.active) > 1 else ""
        if pb.duration:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(min(1.0, elapsed / pb.duration) * 1000))
            self.progress.setFormat(
                f"♪  {pb.title}   {fmt_duration(elapsed)} / {fmt_duration(pb.duration)}{extra}"
            )
        else:
            self.progress.setRange(0, 0)
            self.progress.setFormat(f"♪  {pb.title}{extra}")

    def _on_probed(self, sid, duration):
        s = self._by_id(sid)
        if not s:
            return
        s["duration"] = round(duration, 3)
        self.model.update_row(self.model.row_of(sid))
        for pb in self.player.active:
            if pb.sound_id == sid and not pb.duration:
                pb.duration = duration
        self._schedule_save()

    def _current_category(self):
        item = self.cat_list.currentItem()
        value = item.data(VALUE_ROLE) if item else ALL
        return None if value == ALL else value

    def _refresh_categories(self):
        current = self.proxy.category
        names = self.categories.names(self.sounds)
        counts = {}
        for s in self.sounds:
            counts[s["category"]] = counts.get(s["category"], 0) + 1
        accent = (colors_for(self.settings["theme"]) or colors_for("dark"))["accent"]

        entries = [(tr("All sounds"), ALL, len(self.sounds), accent, "🗂️")]
        if names and counts.get(""):
            entries.append((tr("Uncategorized"), "", counts[""], "#8a8ca0", "📄"))
        for n in names:
            entries.append((n, n, counts.get(n, 0), self.categories.color(n), self.categories.icon(n)))

        self.cat_list.blockSignals(True)
        self.cat_list.clear()
        selected_row = 0
        for i, (label, value, count, color, icon) in enumerate(entries):
            item = QListWidgetItem(label)
            item.setData(VALUE_ROLE, value)
            item.setData(COUNT_ROLE, count)
            item.setData(COLOR_ROLE, color)
            item.setData(ICON_ROLE, icon)
            self.cat_list.addItem(item)
            if (value == ALL and current is None) or value == current:
                selected_row = i
        self.cat_list.setCurrentRow(selected_row)
        self.cat_list.blockSignals(False)
        self.proxy.set_category(self._current_category())
        self.table.viewport().update()

    def _on_category_changed(self, item, _previous):
        if item is not None:
            self.proxy.set_category(self._current_category())

    def _assign_category(self, sounds, category):
        for s in sounds:
            s["category"] = category
            self.model.update_row(self.model.row_of(s["id"]))
        self._refresh_categories()
        self._schedule_save()

    def _on_sounds_dropped(self, ids, category):
        id_set = set(ids)
        moved = [s for s in self.sounds if s["id"] in id_set]
        self._assign_category(moved, category)
        label = category or tr("Uncategorized")
        self.statusBar().showMessage(tr("{n} sound(s) moved to »{category}«.", n=len(moved), category=label), 4000)

    def new_category(self, assign_to=None):
        dlg = CategoryDialog(self, self.categories.names(self.sounds))
        if dlg.exec() != CategoryDialog.Accepted:
            return None
        name = dlg.name()
        self.categories.set(name, dlg.color, dlg.icon)
        if assign_to:
            self._assign_category(assign_to, name)
        else:
            self._refresh_categories()
            self._schedule_save()
        return name

    def edit_category(self, name):
        if not name or name == ALL:
            return
        dlg = CategoryDialog(
            self, self.categories.names(self.sounds), name, self.categories.color(name), self.categories.icon(name)
        )
        if dlg.exec() != CategoryDialog.Accepted:
            return
        new_name = dlg.name()
        if self.proxy.category == name:
            self.proxy.category = new_name
        self.categories.rename(name, new_name, self.sounds)
        self.categories.set(new_name, dlg.color, dlg.icon)
        self.model.reset()
        self._refresh_categories()
        self._schedule_save()

    def delete_category(self, name):
        if not name or name == ALL:
            return
        answer = QMessageBox.question(
            self, APP_NAME,
            tr("Delete category »{name}«? Its sounds stay in the list without a category.", name=name),
        )
        if answer != QMessageBox.Yes:
            return
        self.categories.delete(name, self.sounds)
        if self.proxy.category == name:
            self.proxy.category = None
        self.model.reset()
        self._refresh_categories()
        self._schedule_save()

    def _category_context_menu(self, pos):
        item = self.cat_list.itemAt(pos)
        value = item.data(VALUE_ROLE) if item else None
        m = QMenu(self)
        if value and value != ALL:
            m.addAction("✏️  " + tr("Edit category …"), lambda: self.edit_category(value))
            m.addAction("🗑️  " + tr("Delete category"), lambda: self.delete_category(value))
            m.addSeparator()
        m.addAction("➕  " + tr("New category …"), self.new_category)
        m.exec(self.cat_list.viewport().mapToGlobal(pos))

    def _make_sounds(self, items):
        existing = {s["path"] for s in self.sounds}
        next_id = max((s["id"] for s in self.sounds), default=0) + 1
        result = []
        for item in items:
            if item["path"] in existing:
                continue
            existing.add(item["path"])
            s = {"orig": item["path"], "category": "", "duration": None, "plays": 0, **item, "id": next_id}
            next_id += 1
            result.append(s)
        return result

    def add_paths(self, paths):
        files = []
        for p in map(Path, paths):
            if p.is_dir():
                for root, _dirs, names in os.walk(p):
                    for name in sorted(names, key=str.lower):
                        if Path(name).suffix.lower() in AUDIO_EXT:
                            files.append(Path(root) / name)
            elif p.suffix.lower() == ".spl":
                self.import_spl(str(p))
            elif p.is_file() and p.suffix.lower() in AUDIO_EXT:
                files.append(p)
        category = self.proxy.category or ""
        new = self._make_sounds(
            {"title": f.stem, "path": str(f.resolve()), "category": category} for f in files
        )
        if not new:
            return
        self.model.append(new)
        self._refresh_categories()
        self._schedule_save()
        self._probe_unknown(new)
        self.statusBar().showMessage(tr("{n} sound(s) added.", n=len(new)), 4000)

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("Add sounds"), self.settings["last_dir"], audio_filter())
        if files:
            self._set("last_dir", str(Path(files[0]).parent))
            self.add_paths(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, tr("Add folder with sounds"), self.settings["last_dir"])
        if folder:
            self._set("last_dir", folder)
            self.add_paths([folder])

    def import_spl_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Import Soundpad list"), self.settings["last_dir"],
            f"{tr('Soundpad sound list')} (*.spl);;{tr('All files')} (*)",
        )
        if path:
            self._set("last_dir", str(Path(path).parent))
            self.import_spl(path)

    def _resolve_with_dialog(self, sounds, title):
        folder = QFileDialog.getExistingDirectory(self, title, self.settings["last_dir"])
        if not folder:
            return None
        self._set("last_dir", folder)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return resolve_missing(sounds, [folder])
        finally:
            QApplication.restoreOverrideCursor()

    def _ask_import_mode(self):
        if not self.sounds:
            return "append"
        box = QMessageBox(self)
        box.setWindowTitle(tr("Soundpad import"))
        box.setText(tr("Append the imported sounds to the current list or replace it?"))
        b_append = box.addButton(tr("Append"), QMessageBox.AcceptRole)
        b_replace = box.addButton(tr("Replace"), QMessageBox.DestructiveRole)
        box.addButton(tr("Cancel"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == b_append:
            return "append"
        if box.clickedButton() == b_replace:
            return "replace"
        return None

    def import_spl(self, path):
        try:
            items = parse_spl(path)
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, tr("Could not read the file:") + f"\n{e}")
            return
        if not items:
            QMessageBox.warning(self, APP_NAME, tr("No sounds were found in this file."))
            return

        missing = [s for s in items if not os.path.isfile(s["path"])]
        if missing:
            win = sum(1 for s in missing if is_windows_path(s["orig"]))
            msg = tr("{total} sounds found, {missing} of them with paths that don't exist here.",
                     total=len(items), missing=len(missing))
            if win:
                msg += " " + tr("({n} Windows paths)", n=win)
            msg += "\n\n" + tr(
                "In the next step, choose the folder where the sound files are located on Linux "
                "(e.g. the mounted Windows partition or a copied sound folder). "
                "Subfolders are searched and files are matched by name."
            )
            answer = QMessageBox.information(self, tr("Soundpad import"), msg, QMessageBox.Ok | QMessageBox.Cancel)
            if answer != QMessageBox.Ok:
                return
            self._resolve_with_dialog(items, tr("Folder with your sounds"))

        mode = self._ask_import_mode()
        if mode is None:
            return
        if mode == "replace":
            self.player.stop_all()
            self.sounds.clear()
            self.model.reset()
        new = self._make_sounds(items)
        self.model.append(new)
        self._refresh_categories()
        self._schedule_save()
        self._probe_unknown(new)

        still = sum(1 for s in new if s["id"] in self.model.missing)
        text = tr("{n} sounds imported.", n=len(new))
        if still:
            text += "\n" + tr(
                "{n} files were not found (marked red). Use »Find missing« to search more folders.", n=still
            )
        QMessageBox.information(self, tr("Soundpad import"), text)

    def find_missing_dialog(self):
        if not self.model.missing:
            QMessageBox.information(self, APP_NAME, tr("All sound files are present."))
            return
        targets = [s for s in self.sounds if s["id"] in self.model.missing]
        fixed = self._resolve_with_dialog(targets, tr("Search folder ({n} missing files)", n=len(targets)))
        if fixed is None:
            return
        self.model.reset()
        self._schedule_save()
        self._probe_unknown()
        text = tr("{fixed} files found, {missing} still missing.", fixed=fixed, missing=len(self.model.missing))
        QMessageBox.information(self, APP_NAME, text)

    def remove_selected(self):
        sel = self._selected_sounds()
        if not sel:
            return
        if len(sel) == 1:
            text = tr("Remove »{title}«?", title=sel[0]["title"])
        else:
            text = tr("Remove {n} sounds?", n=len(sel))
        text += "\n" + tr("(The files themselves will not be deleted.)")
        if QMessageBox.question(self, APP_NAME, text) != QMessageBox.Yes:
            return
        ids = {s["id"] for s in sel}
        self.model.remove_rows([i for i, s in enumerate(self.sounds) if s["id"] in ids])
        self._refresh_categories()
        self._schedule_save()

    def _rename(self, s):
        idx = self.proxy.mapFromSource(self.model.index(self.model.row_of(s["id"]), 1))
        if idx.isValid():
            self.table.edit(idx)

    def _relink(self, s):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Choose file for »{title}«", title=s["title"]), self.settings["last_dir"], audio_filter()
        )
        if not path:
            return
        s["path"] = path
        s["duration"] = None
        self.model.refresh_missing()
        self.model.update_row(self.model.row_of(s["id"]))
        self.prober.run([(s["id"], path)])
        self._schedule_save()

    def _copy_command(self, s):
        cmd = f"{cli_command()} --play {s['id']}"
        QGuiApplication.clipboard().setText(cmd)
        self.statusBar().showMessage(tr("Copied: {cmd}", cmd=cmd), 6000)

    def _open_folder(self, s):
        folder = str(Path(s["path"]).parent)
        if os.path.isdir(folder):
            subprocess.Popen(["xdg-open", folder], start_new_session=True)

    def _category_submenu(self, parent, sel):
        sub = parent.addMenu("🏷️  " + tr("Move to category"))
        for name in self.categories.names(self.sounds):
            sub.addAction(f"{self.categories.icon(name)}  {name}",
                          lambda n=name: self._assign_category(sel, n))
        if self.categories.names(self.sounds):
            sub.addSeparator()
        sub.addAction("📄  " + tr("No category"), lambda: self._assign_category(sel, ""))
        sub.addAction("➕  " + tr("New category …"), lambda: self.new_category(assign_to=sel))

    def _sound_context_menu(self, pos):
        sel = self._selected_sounds()
        if not sel:
            return
        s = sel[0]
        single = len(sel) == 1
        m = QMenu(self)
        m.addAction("▶  " + tr("Play"), lambda: self.play(s))
        m.addAction("🎧  " + tr("Play only for me"), lambda: self.play(s, only_self=True))
        m.addSeparator()
        if single:
            m.addAction("✏️  " + tr("Rename  (F2)"), lambda: self._rename(s))
        self._category_submenu(m, sel)
        if single:
            m.addAction("🔗  " + tr("Relink file …"), lambda: self._relink(s))
            m.addAction("⌨️  " + tr("Copy hotkey command"), lambda: self._copy_command(s))
            m.addAction("📂  " + tr("Open folder"), lambda: self._open_folder(s))
        m.addSeparator()
        m.addAction("🗑️  " + tr("Remove  (Del)"), self.remove_selected)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _toggle_window(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._show_window()

    def closeEvent(self, event):
        if not self.quitting and self.tray and self.settings["tray"]:
            self.hide()
            event.ignore()
            return
        self.cleanup()
        event.accept()
        QApplication.quit()

    def quit_app(self):
        self.quitting = True
        self.cleanup()
        QApplication.quit()

    def cleanup(self):
        if self.cleaned_up:
            return
        self.cleaned_up = True
        self.player.stop_all()
        self.router.teardown()
        self.save_timer.stop()
        self._save_now()
        self.server.close()
