import time
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QPushButton
from pointer.cursor.resources import RenderRequest, render_cursor
from pointer.cursor.motion import ClickMotion
from .theme import card


class PreviewSurface(QWidget):
    def __init__(self, owner, theme):
        super().__init__()
        self.owner, self.theme = owner, theme
        self.hovered = False
        self.pressed = False
        self.setMinimumHeight(165)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = True
            self.owner.set_down(True)
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = False
            self.owner.set_down(False)
            self.update()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        self.hovered = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.pressed = False
        self.owner.set_down(False)
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Card container
        rect = self.rect()
        card_rect = QRectF(rect.x() + 1, rect.y() + 1, rect.width() - 2, rect.height() - 2)

        is_light = (self.theme == 'light')
        bg_color = QColor('#f8fafc' if is_light else '#1e293b')
        painter.setBrush(bg_color)

        is_down = bool(self.pressed or self.owner.down)
        if is_down:
            border_pen = QPen(QColor('#2cb6ad'), 2)
        elif self.hovered:
            border_pen = QPen(QColor('#0284c7' if is_light else '#38bdf8'), 1.5)
        else:
            border_pen = QPen(QColor('#e2e8f0' if is_light else '#334155'), 1)

        painter.setPen(border_pen)
        painter.drawRoundedRect(card_rect, 12, 12)

        # Subtle badge at top-left
        badge_rect = QRectF(card_rect.x() + 12, card_rect.y() + 12, 138, 22)
        badge_bg = QColor(255, 255, 255, 200) if is_light else QColor(15, 23, 42, 200)
        badge_border = QColor('#cbd5e1') if is_light else QColor('#475569')
        painter.setBrush(badge_bg)
        painter.setPen(QPen(badge_border, 0.8))
        painter.drawRoundedRect(badge_rect, 11, 11)

        badge_font = QFont('Segoe UI Variable Text', 9)
        badge_font.setWeight(QFont.Weight.Medium)
        painter.setFont(badge_font)

        if is_down:
            painter.setPen(QColor('#2cb6ad'))
            badge_text = '● 动效激发中'
        else:
            painter.setPen(QColor('#64748b' if is_light else '#94a3b8'))
            badge_text = '浅色 · 点击测手感' if is_light else '深色 · 点击测手感'

        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Render Cursor
        settings = self.owner.settings
        role = self.owner.role.currentData() or 'arrow'
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy', 'working') else 0
        image, _ = render_cursor(RenderRequest(settings, role, self.theme, frame))
        data = image.tobytes('raw', 'RGBA')
        qt = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888).copy()

        # Display comfortably within card bounds below the badge without clipping
        avail_w = max(40, self.width() - 32)
        avail_h = max(40, self.height() - 48)
        scale = min(2.0, max(0.5, min(avail_w / image.width, avail_h / image.height)))
        disp_w = int(image.width * scale)
        disp_h = int(image.height * scale)

        dest_x = int((self.width() - disp_w) / 2)
        dest_y = int(28 + (self.height() - 28 - disp_h) / 2)
        painter.drawImage(
            dest_x, dest_y,
            qt.scaled(disp_w, disp_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )


class PreviewPanel(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings, self.frame, self.loading_frame = settings, 0, 0
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        self.down = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        frame, inner = card('实时双态预览', '高精度实时渲染。直接点击卡片或按住下方按钮触发动效。')

        self.role = QComboBox()
        for label, role in [
            ('🎯  普通箭头 (Arrow)', 'arrow'),
            ('👆  链接手型 (Hand)', 'hand'),
            ('📝  文本输入 (IBeam)', 'ibeam'),
            ('⏳  等待加载 (Wait)', 'busy'),
            ('⚙️  后台运行 (AppStarting)', 'working'),
        ]:
            self.role.addItem(label, role)
        self.role.currentIndexChanged.connect(self.refresh)
        inner.addWidget(self.role)

        self.surfaces = [PreviewSurface(self, theme) for theme in ('light', 'dark')]
        for surface in self.surfaces:
            inner.addWidget(surface)

        button = QPushButton('按住预览左键动效')
        button.setObjectName('motionPreviewButton')
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
        for surface in self.surfaces:
            surface.update()

    def tick(self):
        old = self.frame
        self.frame = self.motion.update(self.down, time.monotonic())
        self.loading_frame = (self.loading_frame + 1) % 24
        if old != self.frame or self.role.currentData() in ('busy', 'working'):
            self.refresh()

    def set_settings(self, settings):
        self.settings = settings
        was_down = self.down
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        if was_down:
            self.motion.down = True
        self.refresh()

    def refresh(self):
        for surface in self.surfaces:
            surface.update()
