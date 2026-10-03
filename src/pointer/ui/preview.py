import time
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QPen, QLinearGradient
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

        # Stage background with subtle Apple gradient
        if is_light:
            grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
            grad.setColorAt(0.0, QColor('#ffffff'))
            grad.setColorAt(1.0, QColor('#f5f5f7'))
            painter.setBrush(grad)
        else:
            grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
            grad.setColorAt(0.0, QColor('#202022'))
            grad.setColorAt(1.0, QColor('#161618'))
            painter.setBrush(grad)

        # Border styling with macOS reactive focus ring
        if is_down:
            border_pen = QPen(QColor('#007aff'), 1.8)
        elif self.hovered:
            border_pen = QPen(QColor(0, 122, 255, 140), 1.2)
        else:
            border_pen = QPen(QColor(0, 0, 0, 22) if is_light else QColor(255, 255, 255, 22), 1.0)

        painter.setPen(border_pen)
        painter.drawRoundedRect(card_rect, 12, 12)

        # Badge pill at top-left
        settings = self.owner.settings
        if is_down:
            badge_bg = QColor(0, 122, 255, 30)
            badge_border = QColor('#007aff')
            badge_text_color = QColor('#0a84ff')
            badge_text = '● 动效激发中'
        else:
            if settings.appearance == 'adaptive':
                badge_text = '浅色 · 自适应光标' if is_light else '深色 · 自适应光标'
            elif settings.appearance == 'light':
                badge_text = '浅色 · 锁定方案' if is_light else '深色 · 锁定浅色标'
            else:
                badge_text = '浅色 · 锁定深色标' if is_light else '深色 · 锁定方案'

            if is_light:
                badge_bg = QColor(255, 255, 255, 240)
                badge_border = QColor(0, 0, 0, 28)
                badge_text_color = QColor('#1d1d1f')
            else:
                badge_bg = QColor(44, 44, 46, 220)
                badge_border = QColor(255, 255, 255, 28)
                badge_text_color = QColor('#f5f5f7')

        badge_font = QFont('Segoe UI Variable Text', 9)
        badge_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(badge_font)
        fm = painter.fontMetrics()
        badge_w = max(130.0, float(fm.horizontalAdvance(badge_text) + 20))
        badge_rect = QRectF(card_rect.x() + 12, card_rect.y() + 12, badge_w, 22)

        painter.setBrush(badge_bg)
        painter.setPen(QPen(badge_border, 0.9))
        painter.drawRoundedRect(badge_rect, 11, 11)
        painter.setPen(badge_text_color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Resolve effective theme under current settings appearance strategy
        if settings.appearance in ('light', 'dark'):
            effective_theme = settings.appearance
        else:
            effective_theme = self.theme

        # Render active cursor frame
        role = self.owner.role.currentData() or 'arrow'
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy', 'working') else 0

        cache_key = (
            settings.size, settings.motion, settings.strength, role, effective_theme, frame,
            getattr(settings, effective_theme + '_body'), getattr(settings, effective_theme + '_outline')
        )
        pixmap = self.owner.get_cached_pixmap(cache_key)
        if pixmap is None:
            image, _ = render_cursor(RenderRequest(settings, role, effective_theme, frame))
            data = image.tobytes('raw', 'RGBA')
            qt = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qt)
            self.owner.put_cached_pixmap(cache_key, pixmap)

        # Display comfortably within card bounds below the badge without clipping
        avail_w = max(40, self.width() - 32)
        avail_h = max(40, self.height() - 48)
        scale = min(2.0, max(0.5, min(avail_w / pixmap.width(), avail_h / pixmap.height())))
        disp_w = int(pixmap.width() * scale)
        disp_h = int(pixmap.height() * scale)

        dest_x = int((self.width() - disp_w) / 2)
        dest_y = int(28 + (self.height() - 28 - disp_h) / 2)
        painter.drawPixmap(dest_x, dest_y, disp_w, disp_h, pixmap)


class PreviewPanel(QWidget):
    """High-fidelity dual-mode cursor showcase workbench with live physical feedback."""
    def __init__(self, settings):
        super().__init__()
        self.settings, self.frame, self.loading_frame = settings, 0, 0
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        self.down = False
        self._pixmap_cache = {}
        self._last_loading_time = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        frame, inner = card('双态实时展台', '超高清实时动态渲染。点击卡片或按住下方按钮测试微物理手感。')

        # Selector Header with role
        role_box = QHBoxLayout()
        role_lbl = QLabel('展示类型：')
        role_lbl.setStyleSheet('color: #86868b; font-weight: 500; font-size: 12px;')
        role_box.addWidget(role_lbl)

        self.role = QComboBox()
        for label, role in [
            ('标准箭头 (Arrow)', 'arrow'),
            ('链接手型 (Hand)', 'hand'),
            ('文本输入 (IBeam)', 'ibeam'),
            ('等待加载 (Wait)', 'busy'),
            ('后台运行 (AppStarting)', 'working'),
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
        button = QPushButton('按住测试左键动效微物理')
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

    def get_cached_pixmap(self, key):
        return self._pixmap_cache.get(key)

    def put_cached_pixmap(self, key, pixmap):
        if len(self._pixmap_cache) > 120:
            self._pixmap_cache.clear()
        self._pixmap_cache[key] = pixmap

    def set_down(self, down):
        self.down = down
        for surface in self.surfaces:
            surface.update()

    def tick(self):
        if self.isHidden():
            return
        now = time.monotonic()
        old = self.frame
        self.frame = self.motion.update(self.down, now)

        role = self.role.currentData() or 'arrow'
        loading_changed = False
        if role in ('busy', 'working'):
            if now - self._last_loading_time >= 0.05:
                self.loading_frame = (self.loading_frame + 1) % 24
                self._last_loading_time = now
                loading_changed = True

        if old != self.frame or loading_changed:
            self.refresh()

    def set_settings(self, settings):
        self.settings = settings
        self._pixmap_cache.clear()
        was_down = self.down
        self.motion = ClickMotion(settings.press_ms, settings.release_ms)
        if was_down:
            self.motion.down = True
            self.motion._target = 0.9  # SCALES[-1]
            self.motion._source = 0.9
            self.motion._since = time.monotonic()
        self.refresh()

    def refresh(self):
        for surface in self.surfaces:
            surface.update()
