"""Material workspace with independent window appearance and cursor drafts."""
import sys
from dataclasses import replace
from .family_workspace import cursor_pixmap, DPI_VARIANTS
from pointer.cursor.resources import canvas_size
from PySide6.QtCore import Qt, QEvent, QPoint, QPointF, QRect, QRectF, QSize, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QMenu, QVBoxLayout, QHBoxLayout, QSizePolicy
from .dual_workspace import DualWindow, ObservationSurface
from .approved_workspace import approved_colors
from .sidebar_settings import SidebarAppearance, SidebarControls
from .confirmations import ask_confirmation
from PySide6.QtWidgets import QMessageBox


def transparency_policy():
    """Read-only platform/accessibility preference; no registry/settings writes."""
    from PySide6.QtWidgets import QApplication
    info = dict(platform=QApplication.platformName(), supported=False, high_contrast=False,
                system_transparency=True, composition=False, reason='unsupported platform')
    if info['platform'] == 'offscreen':
        info.update(supported=True, reason='alpha-render test only; no desktop composition')
        return info
    if sys.platform != 'win32' or info['platform'] != 'windows':
        return info
    import ctypes
    from ctypes import wintypes
    class HC(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.UINT), ('dwFlags', wintypes.DWORD), ('scheme', wintypes.LPWSTR)]
    hc = HC(); hc.cbSize = ctypes.sizeof(hc)
    user = ctypes.WinDLL('user32')
    user.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    user.SystemParametersInfoW.restype = wintypes.BOOL
    ok = user.SystemParametersInfoW(0x42, hc.cbSize, ctypes.byref(hc), 0)
    info['high_contrast'] = bool(hc.dwFlags & 1)
    dwm = ctypes.WinDLL('dwmapi')
    composition = wintypes.BOOL()
    dwm.DwmIsCompositionEnabled.argtypes = [ctypes.POINTER(wintypes.BOOL)]
    dwm.DwmIsCompositionEnabled.restype = ctypes.c_long
    info['composition'] = dwm.DwmIsCompositionEnabled(ctypes.byref(composition)) == 0 and bool(composition.value)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            info['system_transparency'] = bool(winreg.QueryValueEx(key, 'EnableTransparency')[0])
    except OSError:
        pass
    info['supported'] = bool(ok and info['composition'] and not info['high_contrast'] and info['system_transparency'])
    info['reason'] = 'Qt Windows alpha window' if info['supported'] else 'opaque accessibility/preference fallback'
    return info


class RoundedObservation(ObservationSurface):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self.theme
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#eef0f5' if theme == 'light' else '#202329'))
        painter.drawRoundedRect(QRectF(self.rect()), 16, 16)
        painter.setPen(QColor('#616979' if theme == 'light' else '#b0b6c2'))
        painter.drawText(self.rect().adjusted(8, 12, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                         '浅色背景' if theme == 'light' else '深色背景')
        settings = self.owner.settings
        effective = settings.appearance if settings.appearance in ('light', 'dark') else theme
        role = self.owner.role.currentData() or 'arrow'
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy', 'working') else 0
        rendered = settings if self.actual else replace(settings, size=64)
        dpi = min(DPI_VARIANTS, key=lambda value: abs(value-96*self.devicePixelRatioF())) if self.actual else 384
        key = (rendered, role, effective, frame, self.actual, dpi)
        pixmap = self.owner.get_cached_pixmap(key)
        if pixmap is None:
            pixmap = cursor_pixmap(rendered, role, effective, frame, crop=not self.actual, dpi=dpi)
            if self.actual:
                pixmap.setDevicePixelRatio(dpi/96)
            self.owner.put_cached_pixmap(key, pixmap)
        if self.actual:
            size = pixmap.deviceIndependentSize()
        else:
            target = max(24, min(140, self.width()-24, self.height()-56))
            pixmap = pixmap.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            size = pixmap.size()
        x, y = (self.width()-size.width())/2, (self.height()-size.height())/2+12
        painter.drawPixmap(QPointF(x, y), pixmap)
        self.cursor_bounds = QRectF(x, y, size.width(), size.height())
        self.last_cursor_key = key
        if (self.hasFocus() and self.property('keyboardFocus')) or self.pressed or self.hovered:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(approved_colors(self.window().ui_dark)['focus']), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 16, 16)
        painter.end()


class RoundedMaterialShell(QWidget):
    """Paint the outer alpha edge once; inner widgets keep transparent edges."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setObjectName('materialWrapper')

    def paintEvent(self, event):
        owner = self.owner
        if not owner._material_ready:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = 0 if owner.isMaximized() else 20
        bounds = QRectF(self.rect())
        rail = owner.material_sidebar.width()
        alpha = (owner.sidebar_appearance.dark_alpha if owner.ui_dark else owner.sidebar_appearance.light_alpha) if owner.sidebar_transparent and owner.material_active else 255
        tint = QColor('#242a34' if owner.ui_dark else '#e3e8f0')
        tint.setAlpha(alpha)
        painter.save()
        painter.setClipRect(QRectF(0, 0, rail, self.height()))
        painter.setBrush(tint)
        painter.drawRoundedRect(bounds, radius, radius)
        painter.restore()
        painter.setClipRect(QRectF(rail, 0, self.width()-rail, self.height()))
        painter.setBrush(QColor(approved_colors(owner.ui_dark)['canvas']))
        painter.drawRoundedRect(bounds, radius, radius)
        painter.end()


class TrafficLightButton(QAbstractButton):
    def __init__(self, owner, name, color, symbol, action):
        super().__init__()
        self.owner, self.color, self.symbol = owner, color, symbol
        self.setObjectName('trafficLight')
        self.setAccessibleName(name)
        self.setToolTip(name)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(32, 32)
        self.clicked.connect(action)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.rect().center()) + QPointF(.5, .5)
        active = self.owner.material_active
        color = QColor(self.color if active else '#73777f' if self.owner.ui_dark else '#c2c5cb')
        if self.isDown():
            color = color.darker(112)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, 7, 7)
        keyboard = self.hasFocus() and self.property('keyboardFocus')
        if self.underMouse() or keyboard:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#452421' if self.symbol == 'close' else '#4f3f19' if self.symbol == 'minimize' else '#145321'), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            x, y = center.x(), center.y()
            if self.symbol == 'close':
                painter.drawLine(QPointF(x-2.5, y-2.5), QPointF(x+2.5, y+2.5))
                painter.drawLine(QPointF(x+2.5, y-2.5), QPointF(x-2.5, y+2.5))
            elif self.symbol == 'minimize':
                painter.drawLine(QPointF(x-3, y), QPointF(x+3, y))
            else:
                for dx, dy in ((-1, -1), (1, 1)):
                    corner = QPointF(x+3*dx, y+3*dy)
                    painter.drawLine(corner, QPointF(x+3*dx, y))
                    painter.drawLine(corner, QPointF(x, y+3*dy))
        if keyboard:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(approved_colors(self.owner.ui_dark)['focus']), 1.5))
            painter.drawEllipse(center, 10, 10)
        painter.end()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event):
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave, QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.update()
        return super().event(event)


class MaterialTitleBar(QFrame):
    def __init__(self, window, previous_layout):
        super().__init__(); self.owner = window
        self.setObjectName('materialPageTitle')
        self.setMinimumHeight(36)
        self.setLayout(previous_layout)
        previous_layout.setContentsMargins(0, 0, 0, 0)
        previous_layout.setSpacing(12)
        window.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        window.page_summary.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.controls = QWidget(window.material_content)
        self.controls.setObjectName('materialWindowControls')
        self.controls.setFixedSize(96, 32)
        lights = QHBoxLayout(self.controls)
        lights.setSpacing(0)
        lights.setContentsMargins(0, 0, 0, 0)
        self.buttons = {}
        for name, color, symbol, action in [('关闭', '#ff5f57', 'close', window.close), ('最小化', '#febc2e', 'minimize', window.showMinimized), ('最大化或还原', '#28c840', 'maximize', window.toggle_maximized)]:
            button = TrafficLightButton(window, name, color, symbol, action)
            lights.addWidget(button)
            self.buttons[name] = button
        # Reserve the same header space at narrow widths; the buttons themselves
        # follow the outer canvas rather than the centered body's width cap.
        previous_layout.addSpacing(self.controls.width())
        window.material_content.installEventFilter(self)

    def _position_controls(self):
        parent = self.controls.parentWidget()
        right = self.owner.content_widget.layout().contentsMargins().right()
        center = self.mapTo(parent, self.rect().center()).y()
        self.controls.move(parent.width()-right-self.controls.width(), center-self.controls.height()//2)
        self.controls.raise_()

    def eventFilter(self, watched, event):
        if watched is self.controls.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            QTimer.singleShot(0, self._position_controls)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_controls()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_controls()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_controls()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner._begin_window_drag(event)
            event.accept(); return
        super().mousePressEvent(event)
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.toggle_maximized(); event.accept(); return
        super().mouseDoubleClickEvent(event)


class MaterialWindow(DualWindow):
    def __init__(self, backend, policy=None, sidebar_store=None, composition_helper=None,
                 composition_error=None, backdrop_host=None):
        self._material_ready = False
        self._composition_helper = composition_helper
        self._composition_error = composition_error
        self._backdrop_host = backdrop_host
        self._backdrop_started = False
        self._backdrop_closing = False
        self._last_backdrop_state = None
        self._policy_override = policy is not None
        self.material_policy = policy or transparency_policy()
        self.sidebar_store = sidebar_store
        self.sidebar_saved = sidebar_store.load() if sidebar_store else SidebarAppearance()
        self.sidebar_appearance = self.sidebar_saved
        self.material_active = True
        self.sidebar_transparent = self.sidebar_appearance.enabled and self.material_policy['supported']
        self._keyboard_operation = None; self.last_system_move = None; self.last_system_resize = None
        self._manual_move_offset = None
        super().__init__(backend)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        root = self.takeCentralWidget(); root.setObjectName('materialShell')
        self.material_sidebar = root.findChild(QFrame, 'referenceSidebar')
        self.material_sidebar.setFixedWidth(200)
        self.material_content = root.layout().itemAt(1).widget()
        self.material_content.setObjectName('materialContent')
        wrapper = RoundedMaterialShell(self)
        self.material_shell = wrapper
        layout = QVBoxLayout(wrapper); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        layout.addWidget(root, 1)
        self.setCentralWidget(wrapper)
        previous_banner = self.title.parentWidget()
        self.content_widget.layout().removeWidget(previous_banner)
        self.title_bar = MaterialTitleBar(self, previous_banner.layout())
        self.content_widget.layout().insertWidget(0, self.title_bar)
        previous_banner.hide()
        self._previous_material_banner = previous_banner
        wrapper.setMouseTracking(True); self.setMouseTracking(True)
        self.content_widget.layout().setContentsMargins(24, 22, 24, 18)
        self.content_widget.layout().setSpacing(20)
        body = self.body_layout.itemAt(0).widget().layout(); body.setSpacing(16); body.setStretch(0,42); body.setStretch(2,58)
        for index in range(self.stack.count()):
            self.stack.widget(index).setViewportMargins(0, 0, 12, 0)
        self.preview.setMinimumWidth(280)
        self.preview.layout().setContentsMargins(0, 8, 0, 8); self.preview.layout().setSpacing(16)
        stages = self.preview.surfaces[0].parentWidget().layout().itemAt(1).layout()
        for surface in self.preview.surfaces: stages.removeWidget(surface); surface.hide()
        self.preview.surfaces = [RoundedObservation(self.preview, theme, actual=True) for theme in ('light','dark')]
        self.preview.hero = self.preview.actual = self.preview.surfaces[0]
        for surface in self.preview.surfaces: stages.addWidget(surface,1)
        stages.setSpacing(12)
        self.observation_role_heading=next(label for label in self.preview.findChildren(QLabel) if label.text()=="光标角色")
        for button in self.preview.role_buttons.values(): button.setFixedHeight(64)
        self.trial_button.setFixedSize(112,40); self.preview.role.setFixedHeight(40)
        for page in (self.pages[0], self.pages[3]):
            page.layout().setSpacing(20)
            for frame in page.findChildren(QFrame):
                if frame.objectName() in ('approvedGroup','referenceGroup'):
                    frame.layout().setContentsMargins(8,8,8,8)
                if frame.objectName() == 'referenceRow':
                    frame.setMinimumHeight(52); frame.layout().setContentsMargins(12,6,12,6)
        self.shape_gallery.layout().setContentsMargins(12,12,12,12); self.shape_gallery.layout().setSpacing(12)
        for button in self.pages[0].shape_buttons.values(): button.setFixedHeight(86); button.setIconSize(QSize(64,48))
        self.palette_gallery.layout().setContentsMargins(12,12,12,12); self.palette_gallery.layout().setSpacing(12)
        for button,_ in self.pages[0].preset_buttons: button.setFixedHeight(76)
        for combo in (self.pages[0].family_size,self.pages[0].family_appearance):
            for button in combo.choice_buttons: button.setMinimumHeight(38)
        for field in self.pages[0].color_fields.values(): field.setMinimumHeight(34)
        self._build_material_footer()
        self.system_menu = QMenu(self)
        for text, action in [('还原',self.showNormal),('移动',lambda:self.begin_keyboard_operation('move')),('调整大小',lambda:self.begin_keyboard_operation('resize')),('最小化',self.showMinimized),('最大化',self.showMaximized),('关闭',self.close)]:
            self.system_menu.addAction(text, action)
        self.system_shortcut = QShortcut(QKeySequence('Alt+Space'), self);self.system_shortcut.activated.connect(self.show_system_menu)
        self.close_shortcut = QShortcut(QKeySequence('Alt+F4'),self);self.close_shortcut.activated.connect(self.close)
        self._material_ready=True
        if self._backdrop_host is None and composition_helper is not None:
            from pointer.windows.composition_host import CompositionHost
            self._backdrop_host = CompositionHost(composition_helper, self)
        if self._backdrop_host is not None:
            self._backdrop_host.ready_changed.connect(self._backdrop_ready_changed)
            self._backdrop_host.failed.connect(self._backdrop_failed)
        self.sidebar_transparent = self._effective_transparency()
        self._apply_reference_theme(); self.resize(1360,920); self.sync()
        for widget in self.findChildren(QWidget): widget.installEventFilter(self)
        self.installEventFilter(self)

    def _preference_groups(self):
        super()._preference_groups()
        self.sidebar_controls = SidebarControls(self)
        self.alpha_toggle = self.sidebar_controls.enabled
        self.pages[3].layout().insertWidget(2, self.sidebar_controls)

    @property
    def sidebar_dirty(self):
        return self.sidebar_appearance != self.sidebar_saved

    @property
    def blur_available(self):
        return bool(self._backdrop_host is not None and self._backdrop_host.ready and not self._composition_error)

    @property
    def composition_error(self):
        return self._composition_error

    def _effective_transparency(self):
        setting = self.sidebar_appearance
        return bool(setting.enabled and self.material_policy['supported'] and
                    (setting.blur == 0 or self.blur_available))

    def _start_sidebar_backdrop(self):
        if self._backdrop_host is not None and not self._backdrop_started and not self._backdrop_closing:
            self._backdrop_started = True
            self._backdrop_host.start(int(self.winId()))
        self._sync_sidebar_backdrop()

    def _backdrop_ready_changed(self, ready):
        if self._backdrop_closing:
            return
        if ready:
            self._composition_error = None
        self.sidebar_transparent = self._effective_transparency()
        self.sidebar_controls.sync()
        self._apply_reference_theme()

    def _backdrop_failed(self, reason):
        self._composition_error = reason
        self._backdrop_ready_changed(False)

    def _sidebar_native_rect(self):
        from PySide6.QtWidgets import QApplication
        point = self.material_sidebar.mapTo(self, QPoint())
        scale = 1.0
        origin_x = origin_y = 0
        if sys.platform == 'win32' and QApplication.platformName() == 'windows':
            import ctypes
            from ctypes import wintypes
            user = ctypes.WinDLL('user32', use_last_error=True)
            user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user.GetClientRect.restype = wintypes.BOOL
            user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            user.ClientToScreen.restype = wintypes.BOOL
            rect, origin = wintypes.RECT(), wintypes.POINT()
            hwnd = int(self.winId())
            if not user.GetClientRect(hwnd, ctypes.byref(rect)) or not user.ClientToScreen(hwnd, ctypes.byref(origin)):
                raise OSError(ctypes.get_last_error(), 'Cannot locate the Pointer client window')
            # Scale local Qt coordinates within this client, never global desktop coordinates.
            scale = (rect.right - rect.left) / max(1, self.width())
            origin_x, origin_y = origin.x, origin.y
        return dict(x=origin_x + round(point.x() * scale), y=origin_y + round(point.y() * scale),
                    width=max(1, round(self.material_sidebar.width() * scale)),
                    height=max(1, round(self.material_sidebar.height() * scale)),
                    radius=0 if self.isMaximized() else round(20 * scale))

    def _sync_sidebar_backdrop(self):
        host = self._backdrop_host
        if not self._material_ready or host is None or self._backdrop_closing or self._composition_error:
            return
        try:
            state = dict(self._sidebar_native_rect(), sigma=self.sidebar_appearance.blur,
                         visible=bool(self.blur_available and self.sidebar_transparent and self.material_active
                                      and self.isVisible() and not self.isMinimized() and self.sidebar_appearance.blur > 0))
        except OSError as error:
            self._backdrop_failed(str(error))
            host.close()
            return
        if state != self._last_backdrop_state:
            self._last_backdrop_state = state
            host.update(state)

    def _close_sidebar_backdrop(self):
        if not self._backdrop_closing:
            self._backdrop_closing = True
            if self._backdrop_host is not None:
                self._backdrop_host.close()

    def _fit_reference_width(self):
        width = self.width()-200 if self._material_ready else self.width()-190
        self.content_widget.setFixedWidth(min(1240,max(0,width)))

    def _build_material_footer(self):
        bar = self.findChild(QFrame, 'controlBar')
        bar.setFixedHeight(64)
        line = bar.layout()
        while line.count():
            line.takeAt(0)
        line.setContentsMargins(0, 8, 0, 8)
        line.setSpacing(12)
        summary = QWidget()
        summary.setObjectName('materialFooterSummary')
        summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        notes = QVBoxLayout(summary)
        notes.setContentsMargins(0, 0, 0, 0)
        notes.setSpacing(2)
        self.draft_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.feedback.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.feedback.setWordWrap(False)
        notes.addWidget(self.draft_label)
        notes.addWidget(self.feedback)
        line.addWidget(summary, 1, Qt.AlignmentFlag.AlignVCenter)
        self.discard.setText('取消')
        self.discard.setObjectName('materialCancel')
        self.discard.setAccessibleName('取消未应用的光标修改')
        self.discard.setFixedSize(64, 38)
        self.apply_button.setFixedSize(112, 38)
        line.addWidget(self.discard)
        line.addWidget(self.apply_button)

    def _apply_reference_theme(self):
        super()._apply_reference_theme()
        if not self._material_ready: return
        c=approved_colors(self.ui_dark)
        self.setStyleSheet(self.styleSheet()+f"""
            QMainWindow, #materialWrapper, #materialShell, #materialContent, #content {{ background: transparent; }}
            #materialPageTitle, #materialWindowControls {{ background: transparent; border: none; }}
            #referenceSidebar {{ background: transparent; border: none; }}
            #navCapsule {{ background: transparent; border: none; }}
            #navCapsule QPushButton {{ border-radius: 10px; min-height: 32px; max-height: 32px; }}
            #navCapsule QPushButton:hover {{ background: {c['raised']}; }}
            #navCapsule QPushButton:checked:hover {{ background: #3472c9; }}
            #navCapsule QPushButton:pressed {{ background: #1e559e; }}
            #approvedGroup, #referenceGroup {{ border-radius: 16px; }}
            QToolButton#approvedShape, QToolButton#paletteSpecimen {{ border-radius: 12px; padding: 8px 4px; }}
            QToolButton[segmented="true"] {{ border-radius: 9px; }}
            QPushButton, QComboBox, QLineEdit {{ border-radius: 9px; }}
            #applyButton {{ border-radius: 10px; }}
            #materialFooterSummary {{ background: transparent; }}
            #controlBar {{ padding: 0; }}
            #materialShell QScrollBar::add-page:vertical,
            #materialShell QScrollBar::sub-page:vertical,
            #materialShell QScrollBar::add-page:horizontal,
            #materialShell QScrollBar::sub-page:horizontal {{ background: transparent; border: none; }}
            #feedback {{ background: transparent; border: none; padding: 0; margin: 0; }}
            QPushButton#materialCancel {{ background: transparent; border: 1px solid transparent; color: {c['muted']}; }}
            QPushButton#materialCancel:hover {{ background: {c['raised']}; color: {c['text']}; }}
            QPushButton#materialCancel:disabled {{ color: {c['disabled_text']}; }}
            QPushButton#materialCancel[keyboardFocus="true"]:focus {{ border-color: {c['focus']}; }}
            QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 8px; }}
            QMenu::item {{ padding: 8px 20px; border-radius: 6px; color: {c['text']}; }}
            QMenu::item:selected {{ background: {c['selected']}; color: white; }}
            QMenu::item:disabled {{ color: {c['muted']}; }}
            QToolButton#approvedShape[keyboardFocus="true"]:focus,
            QToolButton#paletteSpecimen[keyboardFocus="true"]:focus {{ border: 2px solid {c['focus']}; }}
        """)
        self.material_shell.update()
        for button in self.title_bar.buttons.values():
            button.update()
        self._sync_sidebar_backdrop()

    def set_sidebar_transparent(self, enabled):
        self.sidebar_appearance = replace(self.sidebar_appearance, enabled=bool(enabled))
        self.sidebar_transparent = self._effective_transparency()
        self._apply_reference_theme()
        self.sidebar_controls.sync()

    def set_sidebar_transparency(self, value):
        key = 'dark_alpha' if self.ui_dark else 'light_alpha'
        self.sidebar_appearance = replace(self.sidebar_appearance, **{key: 255 - value})
        self._apply_reference_theme()
        self.sidebar_controls.sync()

    def cancel_sidebar_settings(self):
        self.sidebar_appearance = self.sidebar_saved
        self.sidebar_transparent = self._effective_transparency()
        self._apply_reference_theme()
        self.sidebar_controls.sync()

    def set_sidebar_blur(self, value):
        self.sidebar_appearance = replace(self.sidebar_appearance, blur=int(value))
        self.sidebar_transparent = self._effective_transparency()
        self._apply_reference_theme()
        self.sidebar_controls.sync()

    def save_sidebar_settings(self):
        if self.sidebar_store is None:
            self.sidebar_controls.status.setText('此捕获窗口不保存外观，请使用安全预览入口。')
            return
        try:
            self.sidebar_store.save(self.sidebar_appearance)
        except OSError as error:
            self.sidebar_controls.status.setText(f'外观保存失败：{error}。可重试或取消预览。')
            return
        self.sidebar_saved = self.sidebar_appearance
        self.sidebar_controls.sync()
        self.sidebar_controls.status.setText('侧栏外观已保存，重启预览后恢复。')

    def closeEvent(self, event):
        if self.busy:
            super().closeEvent(event)
            return
        if self.sidebar_dirty:
            message = '放弃未保存的侧栏外观和未应用的光标修改并关闭窗口？' if self._draft != self.applied else '放弃侧栏外观预览并关闭窗口？'
            if ask_confirmation(self, '未保存的修改', message, '放弃修改', '继续编辑') != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            event.accept()
            self._close_sidebar_backdrop()
            return
        super().closeEvent(event)
        if event.isAccepted():
            self._close_sidebar_backdrop()

    def refresh_material_policy(self):
        if not self._policy_override:
            self.material_policy = transparency_policy()
        self.sidebar_transparent = self._effective_transparency()
        self.sidebar_controls.sync()
        self._apply_reference_theme()

    def nativeEvent(self, event_type, message):
        if self._material_ready and sys.platform == 'win32' and not self._policy_override:
            import ctypes
            from ctypes import wintypes
            native = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if native.message in (0x001A, 0x031A, 0x031E):
                QTimer.singleShot(0, self.refresh_material_policy)
            elif native.message in (0x0047, 0x02E0):
                QTimer.singleShot(0, self._sync_sidebar_backdrop)
        return super().nativeEvent(event_type, message)

    def sync(self):
        super().sync()
        if self._material_ready:
            self._fit_observation_height()
            self.sidebar_controls.sync()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._material_ready:
            self.material_sidebar.setFixedWidth(200);self.nav_rail.setFixedWidth(200);self._fit_reference_width()
            self._fit_observation_height()
            narrow=self.width()<1000
            self.content_widget.layout().setContentsMargins(18 if narrow else 24,22,18 if narrow else 24,18)
            self.body_layout.itemAt(0).widget().layout().setSpacing(12 if narrow else 16)
            columns=4 if self.width()>=1120 else 2
            page=self.pages[0];page._preset_columns=page._reference_palette_columns=columns
            for index,(button,_) in enumerate(page.preset_buttons):
                page.preset_grid.removeWidget(button);page.preset_grid.addWidget(button,index//columns,index%columns)
            self.palette_gallery.setFixedHeight(188 if columns==4 else 364)
            page.preset_grid.invalidate();page.updateGeometry()
            self._sync_sidebar_backdrop()

    def _fit_observation_height(self):
        height = 232 if self.height() >= 820 else 168 if self.height() >= 700 else 112
        height=max(height,canvas_size(self._draft)+24)
        for surface in self.preview.surfaces: surface.setFixedHeight(height)
        self.observation_role_heading.setVisible(self.height()>=820)
        self.preview.layout().setSpacing(16 if self.height() >= 820 else 8)
        for button in self.preview.role_buttons.values(): button.setFixedHeight(64 if self.height() >= 820 else 52)

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def show_system_menu(self):
        self.system_menu.actions()[0].setEnabled(self.isMaximized() or self.isMinimized())
        self.system_menu.actions()[1].setEnabled(not self.isMaximized())
        self.system_menu.actions()[2].setEnabled(not self.isMaximized())
        self.system_menu.actions()[4].setEnabled(not self.isMaximized())
        self.system_menu.popup(self.title_bar.mapToGlobal(QPoint(12,self.title_bar.height())))

    def begin_keyboard_operation(self, mode):
        if self.isMaximized(): self.showNormal()
        self._keyboard_operation=(mode,self.geometry());self.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def resize_edges(self, point):
        if self.isMaximized(): return Qt.Edge(0)
        edges=Qt.Edge(0)
        if point.x()<6: edges|=Qt.Edge.LeftEdge
        if point.x()>=self.width()-6: edges|=Qt.Edge.RightEdge
        if point.y()<6: edges|=Qt.Edge.TopEdge
        if point.y()>=self.height()-6: edges|=Qt.Edge.BottomEdge
        return edges

    def _is_window_drag_point(self, watched, point):
        if watched.window() is not self or not self.rect().contains(point):
            return False
        header_bottom = (self.title_bar.mapTo(self, QPoint(0, self.title_bar.height())).y()
                         + self.content_widget.layout().spacing())
        if point.y() >= header_bottom:
            return False
        # The header extends across the brand and canvas gutters. Interactive
        # widgets keep their own input even if a parent receives the event.
        child = self.childAt(point) or watched
        while child is not None and child is not self:
            if isinstance(child, (QAbstractButton, QAbstractSlider, QAbstractSpinBox,
                                  QComboBox, QLineEdit, QTextEdit, QPlainTextEdit)):
                return False
            child = child.parentWidget()
        return True

    def _begin_window_drag(self, event):
        self._end_window_drag()
        handle = self.windowHandle()
        self.last_system_move = bool(handle and handle.startSystemMove())
        if self.last_system_move:
            return
        global_pos = event.globalPosition().toPoint()
        if self.isMaximized():
            local = self.mapFromGlobal(global_pos)
            ratio = local.x() / max(1, self.width())
            normal = self.normalGeometry()
            restored_size = normal.size() if normal.isValid() else self.size()
            self.showNormal()
            # Restoration may deliver its resize later. Apply the saved normal
            # size with the pointer anchor so an early move cannot replace it.
            restored_pos = QPoint(global_pos.x()-round(restored_size.width()*ratio),
                                  global_pos.y()-local.y())
            self.setGeometry(QRect(restored_pos, restored_size))
        self._manual_move_offset = global_pos-self.pos()
        self.grabMouse()

    def _end_window_drag(self):
        self._manual_move_offset = None
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()

    def eventFilter(self, watched, event):
        if self._material_ready and watched is self.feedback and event.type()==QEvent.Type.Paint:
            self.feedback.setToolTip(self.feedback.text())
        if (self._material_ready and self._manual_move_offset is not None
                and isinstance(watched, QWidget) and watched.window() is self):
            if event.type() == QEvent.Type.MouseMove:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    self.move(event.globalPosition().toPoint()-self._manual_move_offset)
                else:
                    self._end_window_drag()
                return True
            if ((event.type() == QEvent.Type.MouseButtonRelease
                 and event.button() == Qt.MouseButton.LeftButton)
                    or (event.type() == QEvent.Type.UngrabMouse and watched is self)):
                self._end_window_drag()
                return event.type() == QEvent.Type.MouseButtonRelease
        if self._material_ready and event.type()==QEvent.Type.MouseMove and isinstance(watched,QWidget) and watched.window() is self:
            edges=self.resize_edges(watched.mapTo(self,event.position().toPoint()))
            if edges:
                diagonal = bool(edges & (Qt.Edge.LeftEdge|Qt.Edge.RightEdge)) and bool(edges & (Qt.Edge.TopEdge|Qt.Edge.BottomEdge))
                cursor = Qt.CursorShape.SizeFDiagCursor if edges in (Qt.Edge.LeftEdge|Qt.Edge.TopEdge,Qt.Edge.RightEdge|Qt.Edge.BottomEdge) else Qt.CursorShape.SizeBDiagCursor if diagonal else Qt.CursorShape.SizeHorCursor if edges & (Qt.Edge.LeftEdge|Qt.Edge.RightEdge) else Qt.CursorShape.SizeVerCursor
                watched.setCursor(cursor); watched.setProperty('resizeCursorSet',True)
            elif watched.property('resizeCursorSet'):
                watched.unsetCursor();watched.setProperty('resizeCursorSet',False)
        if self._material_ready and event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton and isinstance(watched,QWidget) and watched.window() is self:
            point = watched.mapTo(self,event.position().toPoint())
            edges=self.resize_edges(point)
            if edges and self.windowHandle():
                self.last_system_resize=self.windowHandle().startSystemResize(edges);return True
            if self._is_window_drag_point(watched, point):
                self._begin_window_drag(event)
                return True
        if self._material_ready and event.type()==QEvent.Type.MouseButtonDblClick and event.button()==Qt.MouseButton.LeftButton and isinstance(watched,QWidget) and watched.window() is self:
            if self._is_window_drag_point(watched, watched.mapTo(self,event.position().toPoint())):
                self._end_window_drag()
                self.toggle_maximized()
                return True
        if self._material_ready and self._keyboard_operation and event.type()==QEvent.Type.KeyPress:
            mode,original=self._keyboard_operation
            if event.key()==Qt.Key.Key_Escape: self.setGeometry(original);self._keyboard_operation=None;return True
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self._keyboard_operation=None;return True
            delta={Qt.Key.Key_Left:(-8,0),Qt.Key.Key_Right:(8,0),Qt.Key.Key_Up:(0,-8),Qt.Key.Key_Down:(0,8)}.get(event.key())
            if delta:
                x,y=delta
                if mode=='move':self.move(self.x()+x,self.y()+y)
                else:self.resize(max(self.minimumWidth(),self.width()+x),max(self.minimumHeight(),self.height()+y))
                return True
        return super().eventFilter(watched,event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._material_ready:
            self.material_active=self.isActiveWindow()
            self._apply_reference_theme()
            QTimer.singleShot(0, self._start_sidebar_backdrop)

    def hideEvent(self, event):
        self._end_window_drag()
        super().hideEvent(event)
        self._sync_sidebar_backdrop()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._sync_sidebar_backdrop()

    def event(self, event):
        if self._material_ready and event.type() in (QEvent.Type.WindowActivate, QEvent.Type.WindowDeactivate):
            if event.type() == QEvent.Type.WindowDeactivate:
                self._end_window_drag()
            self.material_active = event.type() == QEvent.Type.WindowActivate
            if self.material_active:
                self.refresh_material_policy()
            self._apply_reference_theme()
        if self._material_ready and event.type() == QEvent.Type.WindowStateChange:
            self._apply_reference_theme()
        return super().event(event)
