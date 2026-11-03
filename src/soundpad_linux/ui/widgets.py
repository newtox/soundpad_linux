from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractItemView, QApplication, QLabel, QListWidget, QSlider, QStyle, QTableView

from ..models import SOUND_IDS_MIME, decode_ids

VALUE_ROLE = Qt.UserRole
COUNT_ROLE = Qt.UserRole + 1
COLOR_ROLE = Qt.UserRole + 2
ICON_ROLE = Qt.UserRole + 3
ALL = "\x00all"


def app_icon():
    icon = QIcon.fromTheme("audio-volume-high")
    if icon.isNull():
        icon = QApplication.style().standardIcon(QStyle.SP_MediaVolume)
    return icon


class SoundTable(QTableView):
    playRequested = Signal()
    deleteRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.MoveAction)

    def keyPressEvent(self, event):
        if self.state() != QAbstractItemView.EditingState:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.playRequested.emit()
                return
            if event.key() == Qt.Key_Delete:
                self.deleteRequested.emit()
                return
        super().keyPressEvent(event)


class CategoryList(QListWidget):
    soundsDropped = Signal(list, str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def _target(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is None or item.data(VALUE_ROLE) == ALL:
            return None
        return item

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SOUND_IDS_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        item = self._target(event) if event.mimeData().hasFormat(SOUND_IDS_MIME) else None
        if item is None:
            event.ignore()
            return
        self.setCurrentItem(item)
        event.acceptProposedAction()

    def dropEvent(self, event):
        item = self._target(event) if event.mimeData().hasFormat(SOUND_IDS_MIME) else None
        if item is None:
            event.ignore()
            return
        self.soundsDropped.emit(decode_ids(event.mimeData()), item.data(VALUE_ROLE))
        event.acceptProposedAction()


class VolumeSlider(QSlider):
    def __init__(self, value, on_change):
        super().__init__(Qt.Horizontal)
        self.setRange(0, 150)
        self.setValue(int(value))
        self.label = QLabel(f"{self.value()} %")
        self.label.setMinimumWidth(50)
        self.valueChanged.connect(lambda v: (self.label.setText(f"{v} %"), on_change(v)))
