import time
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QFrame
from pointer.cursor.resources import RenderRequest, render_cursor
from pointer.cursor.motion import ClickMotion
from .theme import card


class PreviewSurface(QWidget):
    """Interactive preview canvas with physics reactivity and multi-theme simulation."""
    def __init__(self, owner, theme):
        super().__init__()
        self.owner, self.theme = owner, theme
        self.hovered = False
        self.pressed = False
        self.setMinimumHeight(170)
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

        rect = self.rect()
        card_rect = QRectF(rect.x() + 1.5, rect.y() + 1.5, rect.width() - 3, rect.height() - 3)

        is_light = (self.theme == 'light')
        is_down = bool(self.pressed or self.owner.down)

        # Stage background with subtle gradient
        if is_light:
            grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
            grad.setColorAt(0.0, QColor('#ffffff'))
            grad.setColorAt(1.0, QColor('#f1f5f9'))
            painter.setBrush(grad)
        else:
            grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
            grad.setColorAt(0.0, QColor('#0f172a'))
            grad.setColorAt(1.0, QColor('#090d16'))
            painter.setBrush(grad)

        # Border styling with reactive glow
        if is_down:
            border_pen = QPen(QColor('#2cb6ad'), 2.2)
        elif self.hovered:
            border_pen = QPen(QColor('#38bdf8' if not is_light else '#0284c7'), 1.8)
        else:
            border_pen = QPen(QColor('#cbd5e1' if is_light else '#334155'), 1.2)

        painter.setPen(border_pen)
        painter.drawRoundedRect(card_rect, 13, 13)

        # Badge pill at top-left
        badge_rect = QRectF(card_rect.x() + 12, card_rect.y() + 12, 142, 22)
        if is_down:
            badge_bg = QColor(44, 182, 173, 40)
            badge_border = QColor('#2cb6ad')
            badge_text_color = QColor('#2cb6ad')
            badge_text = '● 动效激发中'
        else:
            if is_light:
                badge_bg = QColor(241, 245, 249, 230)
                badge_border = QColor('#94a3b8')
                badge_text_color = QColor('#475569')
                badge_text = '浅色 · 点击测手感'
            else:
                badge_bg = QColor(30, 41, 59, 230)
                badge_border = QColor('#475569')
                badge_text_color = QColor('#94a3b8')
                badge_text = '深色 · 点击测手感'

        painter.setBrush(badge_bg)
        painter.setPen(QPen(badge_border, 0.9))
        painter.drawRoundedRect(badge_rect, 11, 11)

        badge_font = QFont('Segoe UI Variable Text', 9)
        badge_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(badge_font)
        painter.setPen(badge_text_color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Render active cursor frame
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
    """High-fidelity dual-mode cursor showcase workbench with live physical feedback."""
    def __init__(self, settings):
        super().__init__()
        self.settings, self.frame, self.loading_frame = settings, 0, 0
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        self.down = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame, inner = card('✦ 双态实时展台', '超高清实时动态渲染。点击卡片或按住下方按钮测试微物理手感。')

        # Selector Header with role
        role_box = QHBoxLayout()
        role_lbl = QLabel('展示类型：')
        role_lbl.setStyleSheet('color: #94a3b8; font-weight: 600; font-size: 12px;')
        role_box.addWidget(role_lbl)

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
        role_box.addWidget(self.role, 1)
        inner.addLayout(role_box)

        # Dual Surfaces (Daylight & Midnight)
        self.surfaces = [PreviewSurface(self, theme) for theme in ('light', 'dark')]
        for surface in self.surfaces:
            inner.addWidget(surface)

        # Physics Trigger Button
        button = QPushButton('⚡ 按住预览左键动效微物理')
        button.setObjectName('motionPreviewButton')
        button.setCursor(Qt.CursorShape.PointingHandCursor)
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
