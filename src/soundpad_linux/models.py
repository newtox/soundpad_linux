import os
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QByteArray, QMimeData, QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QFont

from .i18n import tr
from .theme import MISSING
from .util import fmt_duration

SORT_ROLE = Qt.UserRole + 1
SOUND_IDS_MIME = "application/x-soundpad-linux-ids"
MISSING_COLOR = QColor(MISSING)
CATEGORY_COLUMN = 2


def column_titles():
    return [tr("No."), tr("Title"), tr("Category"), tr("Duration"), tr("Played")]


def encode_ids(ids):
    mime = QMimeData()
    mime.setData(SOUND_IDS_MIME, QByteArray(",".join(str(i) for i in ids).encode()))
    return mime


def decode_ids(mime):
    raw = bytes(mime.data(SOUND_IDS_MIME)).decode()
    return [int(x) for x in raw.split(",") if x.isdigit()]


class SoundModel(QAbstractTableModel):
    edited = Signal()

    def __init__(self, sounds):
        super().__init__()
        self.sounds = sounds
        self.playing = set()
        self.missing = set()
        self.refresh_missing()

    def refresh_missing(self):
        self.missing = {s["id"] for s in self.sounds if not os.path.isfile(s["path"])}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.sounds)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 5

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return column_titles()[section]
        return None

    @staticmethod
    def _display(s, col):
        return (
            str(s["id"]),
            s["title"],
            s["category"],
            fmt_duration(s.get("duration")),
            str(s.get("plays", 0)),
        )[col]

    @staticmethod
    def _sort_key(s, col):
        return (
            s["id"],
            s["title"].lower(),
            s["category"].lower(),
            s.get("duration") or 0.0,
            s.get("plays", 0),
        )[col]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        s = self.sounds[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._display(s, col)
        if role == SORT_ROLE:
            return self._sort_key(s, col)
        if role == Qt.ForegroundRole and s["id"] in self.missing:
            return MISSING_COLOR
        if role == Qt.FontRole and s["id"] in self.playing:
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ToolTipRole:
            if s["id"] in self.missing:
                return tr("File not found:") + "\n" + s["path"]
            return s["path"]
        if role == Qt.TextAlignmentRole and col in (0, 3, 4):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.UserRole:
            return s["id"]
        return None

    def flags(self, index):
        f = super().flags(index)
        if index.isValid():
            f |= Qt.ItemIsDragEnabled
            if index.column() in (1, 2):
                f |= Qt.ItemIsEditable
        return f

    def mimeTypes(self):
        return [SOUND_IDS_MIME]

    def mimeData(self, indexes):
        rows = sorted({i.row() for i in indexes if i.isValid()})
        return encode_ids(self.sounds[r]["id"] for r in rows)

    def supportedDragActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False
        s = self.sounds[index.row()]
        value = str(value).strip()
        if index.column() == 1 and value:
            s["title"] = value
        elif index.column() == 2:
            s["category"] = value
        else:
            return False
        self.dataChanged.emit(index, index)
        self.edited.emit()
        return True

    def row_of(self, sid):
        for i, s in enumerate(self.sounds):
            if s["id"] == sid:
                return i
        return -1

    def update_row(self, row):
        if row >= 0:
            self.dataChanged.emit(self.index(row, 0), self.index(row, 5 - 1))

    def set_playing(self, ids):
        if ids == self.playing:
            return
        changed = ids ^ self.playing
        self.playing = set(ids)
        for sid in changed:
            self.update_row(self.row_of(sid))

    def append(self, new_sounds):
        if not new_sounds:
            return
        start = len(self.sounds)
        self.beginInsertRows(QModelIndex(), start, start + len(new_sounds) - 1)
        self.sounds.extend(new_sounds)
        self.missing |= {s["id"] for s in new_sounds if not os.path.isfile(s["path"])}
        self.endInsertRows()

    def remove_rows(self, rows):
        for row in sorted(set(rows), reverse=True):
            self.beginRemoveRows(QModelIndex(), row, row)
            self.missing.discard(self.sounds[row]["id"])
            del self.sounds[row]
            self.endRemoveRows()

    def reset(self):
        self.beginResetModel()
        self.refresh_missing()
        self.endResetModel()


class FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.category = None
        self.text = ""
        self.setSortRole(SORT_ROLE)

    def set_category(self, category):
        self.category = category
        self.invalidate()

    def set_text(self, text):
        self.text = text.strip().lower()
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        s = self.sourceModel().sounds[row]
        if self.category is not None and s["category"] != self.category:
            return False
        if self.text:
            hay = f"{s['id']} {s['title']} {s['category']} {Path(s['path']).name}".lower()
            return all(word in hay for word in self.text.split())
        return True
