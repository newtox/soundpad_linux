from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..categories import DEFAULT_ICON, ICONS, PALETTE, default_color
from ..i18n import tr
from .delegates import contrast_text


class CategoryDialog(QDialog):
    def __init__(self, parent, existing, name="", color=None, icon=None):
        super().__init__(parent)
        self.existing = {n.lower() for n in existing if n != name}
        self.color = color or default_color(name or "new")
        self.icon = icon or DEFAULT_ICON
        self.setWindowTitle(tr("Edit category") if name else tr("New category"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(44)
        layout.addWidget(self.preview)

        layout.addWidget(QLabel(tr("Name")))
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText(tr("e.g. Memes"))
        self.name_edit.textChanged.connect(self._update)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(tr("Color")))
        colors = QHBoxLayout()
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for c in PALETTE:
            b = self._swatch(c)
            b.setChecked(c.lower() == self.color.lower())
            colors.addWidget(b)
        custom = QPushButton(tr("Custom …"))
        custom.clicked.connect(self._pick_custom)
        colors.addWidget(custom)
        colors.addStretch(1)
        layout.addLayout(colors)

        layout.addWidget(QLabel(tr("Icon")))
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        self.icon_group = QButtonGroup(self)
        self.icon_group.setExclusive(True)
        for i, emoji in enumerate(ICONS):
            b = QPushButton(emoji)
            b.setObjectName("emoji")
            b.setCheckable(True)
            b.setFixedSize(38, 38)
            b.setChecked(emoji == self.icon)
            b.clicked.connect(lambda _c=False, e=emoji: self._set_icon(e))
            self.icon_group.addButton(b)
            grid.addWidget(b, i // 12, i % 12)
        layout.addWidget(grid_widget)

        self.error = QLabel()
        self.error.setStyleSheet("color: #ef4b5c;")
        layout.addWidget(self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("Save"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        layout.addWidget(buttons)
        self._update()

    def _swatch(self, color):
        b = QPushButton()
        b.setObjectName("swatch")
        b.setCheckable(True)
        b.setFixedSize(28, 28)
        b.setStyleSheet(f"QPushButton#swatch {{ background: {color}; }}")
        b.clicked.connect(lambda _c=False, c=color: self._set_color(c))
        self.color_group.addButton(b)
        return b

    def _pick_custom(self):
        c = QColorDialog.getColor(QColor(self.color), self, tr("Choose color"))
        if c.isValid():
            for b in self.color_group.buttons():
                b.setChecked(False)
            self._set_color(c.name())

    def _set_color(self, color):
        self.color = color
        self._update()

    def _set_icon(self, icon):
        self.icon = icon
        self._update()

    def name(self):
        return self.name_edit.text().strip()

    def _update(self):
        name = self.name() or tr("Category")
        text_color = contrast_text(QColor(self.color)).name()
        self.preview.setText(f"{self.icon}  {name}")
        self.preview.setStyleSheet(
            f"background: {self.color}; color: {text_color}; border-radius: 22px; "
            "font-size: 16px; font-weight: 700; padding: 8px 18px;"
        )
        duplicate = self.name().lower() in self.existing
        self.error.setText(tr("A category with this name already exists.") if duplicate else "")
        self.ok_button.setEnabled(bool(self.name()) and not duplicate)

    def _accept(self):
        if self.ok_button.isEnabled():
            self.accept()
