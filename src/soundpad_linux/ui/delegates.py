from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from .widgets import COLOR_ROLE, COUNT_ROLE, ICON_ROLE


def contrast_text(color):
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return QColor("#15151c") if luminance > 150 else QColor("#ffffff")


def _draw_base(option, index, painter, delegate):
    opt = QStyleOptionViewItem(option)
    delegate.initStyleOption(opt, index)
    opt.text = ""
    style = opt.widget.style() if opt.widget else QApplication.style()
    style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)


class CategoryChipDelegate(QStyledItemDelegate):
    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.categories = categories

    def paint(self, painter, option, index):
        name = index.data(Qt.DisplayRole)
        if not name:
            super().paint(painter, option, index)
            return
        _draw_base(option, index, painter, self)
        color = QColor(self.categories.color(name))
        text = f"{self.categories.icon(name)}  {name}"
        fm = option.fontMetrics
        r = option.rect.adjusted(6, 4, -6, -4)
        chip = QRect(r.left(), r.top(), min(r.width(), fm.horizontalAdvance(text) + 20), r.height())
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(chip, chip.height() / 2, chip.height() / 2)
        painter.setPen(contrast_text(color))
        f = QFont(option.font)
        f.setBold(True)
        painter.setFont(f)
        inner = chip.adjusted(10, 0, -8, 0)
        painter.drawText(inner, Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(text, Qt.ElideRight, inner.width()))
        painter.restore()


class CategoryListDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(160, max(38, option.fontMetrics.height() + 18))

    def paint(self, painter, option, index):
        pal = option.palette
        color = QColor(index.data(COLOR_ROLE) or pal.highlight().color())
        icon = index.data(ICON_ROLE) or ""
        count = index.data(COUNT_ROLE)
        name = index.data(Qt.DisplayRole) or ""
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = option.rect.adjusted(3, 2, -3, -2)
        painter.setPen(Qt.NoPen)
        if selected or hovered:
            bg = QColor(color)
            bg.setAlpha(75 if selected else 30)
            painter.setBrush(bg)
            painter.drawRoundedRect(r, 9, 9)
        if selected:
            painter.setBrush(color)
            painter.drawRoundedRect(QRect(r.left(), r.top() + 6, 4, r.height() - 12), 2, 2)

        badge = QRect(r.left() + 10, r.center().y() - 12, 25, 25)
        painter.setBrush(color)
        painter.drawRoundedRect(badge, 7, 7)
        painter.setPen(contrast_text(color))
        painter.drawText(badge, Qt.AlignCenter, icon)

        fm = option.fontMetrics
        count_text = str(count) if count is not None else ""
        pill_w = fm.horizontalAdvance(count_text) + 14 if count_text else 0
        pill = QRect(r.right() - pill_w - 8, r.center().y() - 10, pill_w, 20)
        if count_text:
            pill_bg = QColor(pal.text().color())
            pill_bg.setAlpha(28)
            painter.setPen(Qt.NoPen)
            painter.setBrush(pill_bg)
            painter.drawRoundedRect(pill, 10, 10)
            painter.setPen(pal.text().color())
            painter.drawText(pill, Qt.AlignCenter, count_text)

        f = QFont(option.font)
        f.setBold(selected)
        painter.setFont(f)
        painter.setPen(pal.text().color())
        text_rect = QRect(badge.right() + 10, r.top(), pill.left() - badge.right() - 16, r.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         painter.fontMetrics().elidedText(name, Qt.ElideRight, text_rect.width()))
        painter.restore()
