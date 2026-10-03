from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton
from pointer.cursor.resources import RenderRequest, render_cursor
from pointer.cursor.motion import ClickMotion
from .theme import card


class PreviewSurface(QWidget):
    def __init__(self, owner, theme):
        super().__init__()
        self.owner, self.theme = owner, theme
        self.setMinimumHeight(155)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#fafbfc' if self.theme == 'light' else '#26303b'))
        painter.drawRoundedRect(self.rect(), 10, 10)
        settings, role = self.owner.settings, self.owner.role.currentData()
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy','working') else 0
        image, _ = render_cursor(RenderRequest(settings, role, self.theme, frame))
        data = image.tobytes('raw', 'RGBA')
        qt = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888).copy()
        # Display at twice the logical size while preserving the actual renderer.
        width = image.width * 2
        painter.drawImage((self.width()-width)//2, (self.height()-width)//2, qt.scaled(width, width, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        painter.setPen(QColor('#7c8792' if self.theme == 'light' else '#a5b2bf'))
        painter.drawText(13, 23, '浅色背景' if self.theme == 'light' else '深色背景')


class PreviewPanel(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings, self.frame, self.loading_frame = settings, 0, 0
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        self.down = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        frame, inner = card('实时预览', '预览草稿效果。应用后可在测试页体验系统光标。')
        self.role = QComboBox()
        for label, role in [('箭头','arrow'),('小手','hand'),('文字输入','ibeam'),('等待','busy'),('后台忙碌','working')]:
            self.role.addItem(label, role)
        self.role.currentIndexChanged.connect(self.refresh)
        inner.addWidget(self.role)
        self.surfaces = [PreviewSurface(self, theme) for theme in ('light','dark')]
        for surface in self.surfaces:
            inner.addWidget(surface)
        button = QPushButton('按住预览左键动效')
        button.pressed.connect(lambda: self.set_down(True))
        button.released.connect(lambda: self.set_down(False))
        inner.addWidget(button)
        layout.addWidget(frame)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def set_down(self, down):
        self.down = down

    def tick(self):
        import time
        old = self.frame
        self.frame = self.motion.update(self.down, time.monotonic())
        self.loading_frame = (self.loading_frame + 1) % 24
        if old != self.frame or self.role.currentData() in ('busy','working'):
            self.refresh()

    def set_settings(self, settings):
        self.settings = settings
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        self.frame = 0
        self.refresh()

    def refresh(self):
        for surface in self.surfaces:
            surface.update()
