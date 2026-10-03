from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QColorDialog
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter
from pointer.cursor.settings import CursorSettings
from ..theme import card


class AppearancePage(QWidget):
    def __init__(self, change):
        super().__init__()
        self.change, self.colors = change, {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        frame, inner = card('背景与配色', '自动适应鼠标所在位置的亮度，保留清晰的主体与边框。')
        self.appearance = QComboBox()
        self.appearance.setObjectName('appearanceCombo')
        for text, value in [('自动适应背景','adaptive'),('固定浅色背景方案','light'),('固定深色背景方案','dark')]:
            self.appearance.addItem(text, value)
        self.appearance.currentIndexChanged.connect(lambda: change(appearance=self.appearance.currentData()))
        inner.addWidget(self.appearance)
        for theme, text in [('light','浅色背景'),('dark','深色背景')]:
            inner.addWidget(QLabel(text))
            row = QHBoxLayout()
            for part, name in [('body','主体'),('outline','边框')]:
                field = theme + '_' + part
                button = QPushButton()
                button.setObjectName(field+'Color')
                button.clicked.connect(lambda checked=False, field=field: self.pick_color(field))
                self.colors[field] = (button, name)
                row.addWidget(button)
            inner.addLayout(row)
        layout.addWidget(frame)
        frame, inner = card('光标大小', '尺寸随 Windows 显示缩放比例调整。')
        self.size = QComboBox()
        self.size.setObjectName('sizeCombo')
        for size in (24,32,40,48,64):
            self.size.addItem(f'{size} px' + ('   默认' if size == 32 else ''), size)
        self.size.currentIndexChanged.connect(lambda: change(size=self.size.currentData()))
        inner.addWidget(self.size)
        layout.addWidget(frame)
        layout.addStretch()

    def pick_color(self, field):
        color = QColorDialog.getColor(QColor(getattr(self.settings, field)), self, '选择光标颜色')
        if color.isValid():
            self.change(**{field:color.name()})

    def sync(self, settings):
        self.settings = settings
        for combo, value in [(self.appearance,settings.appearance),(self.size,settings.size)]:
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)
        for field, (button,name) in self.colors.items():
            color = getattr(settings, field)
            button.setText(f'{name}   {color.upper()}')
            swatch = QPixmap(18,18)
            swatch.fill(QColor('transparent'))
            painter = QPainter(swatch)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor('#b6c2ca'))
            painter.setBrush(QColor(color))
            painter.drawEllipse(1,1,15,15)
            painter.end()
            button.setIcon(QIcon(swatch))
            button.setIconSize(QSize(18,18))
