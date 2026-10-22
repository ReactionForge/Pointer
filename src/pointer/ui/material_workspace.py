"""Material workspace with independent window appearance and cursor drafts."""
import sys
from dataclasses import replace
from .family_workspace import cursor_pixmap, DPI_VARIANTS
from pointer.cursor.resources import canvas_size
from PySide6.QtCore import Qt, QEvent, QPoint, QPointF, QRect, QRectF, QSize, QTimer, Slot
from PySide6.QtGui import QShortcut, QKeySequence, QPainter, QColor, QPen, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QMenu, QVBoxLayout, QHBoxLayout, QSizePolicy
from .dual_workspace import DualWindow, ObservationSurface
from .approved_workspace import approved_colors
from .sidebar_settings import SidebarAppearance, SidebarControls
from .confirmations import ask_confirmation
from PySide6.QtWidgets import QMessageBox, QApplication, QProgressBar
from .operation_feedback import FeedbackLabel, FeedbackDetails
from .theme import scrollbar_style


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

    @property
    def is_fallback(self):
        owner = self.owner
        if not getattr(owner, 'sidebar_transparent', False) or not getattr(owner, 'material_active', False):
            return True
        if getattr(owner, '_composition_error', None):
            return True
        policy = getattr(owner, 'material_policy', None) or {}
        if not policy.get('supported', True) or policy.get('high_contrast', False):
            return True
        return False

    def paintEvent(self, event):
        owner = self.owner
        if not owner._material_ready:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = 0 if owner.isMaximized() else 20
        bounds = QRectF(self.rect())
        full_window = getattr(owner, 'full_window_backdrop', False)
        fallback = self.is_fallback

        if full_window:
            if fallback:
                # 100% opaque fluid gradient fallback (#141221 -> #161a29 -> #0e131f)
                gradient = QLinearGradient(0, 0, self.width(), self.height())
                if owner.ui_dark:
                    gradient.setColorAt(0.0, QColor('#141221'))
                    gradient.setColorAt(0.5, QColor('#161a29'))
                    gradient.setColorAt(1.0, QColor('#0e131f'))
                else:
                    gradient.setColorAt(0.0, QColor('#edf1f7'))
                    gradient.setColorAt(0.5, QColor('#e2e7f2'))
                    gradient.setColorAt(1.0, QColor('#d8dfed'))
                painter.setBrush(gradient)
                painter.drawRoundedRect(bounds, radius, radius)
            else:
                # Translucent dark wash base with diffuse violet/cyan glows when active
                if owner.sidebar_appearance is not None:
                    alpha = owner.sidebar_appearance.dark_alpha if owner.ui_dark else owner.sidebar_appearance.light_alpha
                else:
                    alpha = 184 if owner.ui_dark else 208
                if owner.ui_dark:
                    wash = QColor(13, 11, 26, alpha)
                    painter.setBrush(wash)
                    painter.drawRoundedRect(bounds, radius, radius)

                    # Diffuse violet glow (top-left)
                    violet_radius = max(self.width(), self.height()) * 0.75
                    violet_glow = QRadialGradient(0, 0, violet_radius)
                    violet_glow.setColorAt(0.0, QColor(139, 92, 246, 55))
                    violet_glow.setColorAt(0.5, QColor(124, 58, 237, 22))
                    violet_glow.setColorAt(1.0, QColor(124, 58, 237, 0))
                    painter.setBrush(violet_glow)
                    painter.drawRoundedRect(bounds, radius, radius)

                    # Diffuse cyan glow (bottom-right)
                    cyan_radius = max(self.width(), self.height()) * 0.75
                    cyan_glow = QRadialGradient(self.width(), self.height(), cyan_radius)
                    cyan_glow.setColorAt(0.0, QColor(6, 182, 212, 45))
                    cyan_glow.setColorAt(0.5, QColor(6, 182, 212, 18))
                    cyan_glow.setColorAt(1.0, QColor(6, 182, 212, 0))
                    painter.setBrush(cyan_glow)
                    painter.drawRoundedRect(bounds, radius, radius)
                else:
                    wash = QColor(237, 241, 247, alpha)
                    painter.setBrush(wash)
                    painter.drawRoundedRect(bounds, radius, radius)

                    glow_radius = max(self.width(), self.height()) * 0.75
                    top_glow = QRadialGradient(0, 0, glow_radius)
                    top_glow.setColorAt(0.0, QColor(167, 139, 250, 35))
                    top_glow.setColorAt(1.0, QColor(167, 139, 250, 0))
                    painter.setBrush(top_glow)
                    painter.drawRoundedRect(bounds, radius, radius)

                    bottom_glow = QRadialGradient(self.width(), self.height(), glow_radius)
                    bottom_glow.setColorAt(0.0, QColor(56, 189, 248, 25))
                    bottom_glow.setColorAt(1.0, QColor(56, 189, 248, 0))
                    painter.setBrush(bottom_glow)
                    painter.drawRoundedRect(bounds, radius, radius)
        else:
            # Partition mode: sidebar rail + opaque canvas
            rail = owner.material_sidebar.width()
            if owner.sidebar_appearance is not None:
                alpha = (owner.sidebar_appearance.dark_alpha if owner.ui_dark else owner.sidebar_appearance.light_alpha) if not fallback else 255
            else:
                alpha = (184 if owner.ui_dark else 208) if not fallback else 255
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
            QTimer.singleShot(0, self, self._position_controls)
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
                 composition_error=None, backdrop_host=None, full_window_backdrop=False):
        self._material_ready = False
        self._feedback_retry = None
        self._feedback_retry_text = ''
        self._feedback_dialog = None
        self._cursor_apply_requested = False
        self._operation_cursor_apply = False
        self._operation_retry = None
        self._failure_text = ''
        self._combined_apply_saved = False
        self.full_window_backdrop = bool(full_window_backdrop)
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
        self.pages[2].navigate_requested.connect(self._navigate_test_context)
        self.page_shortcuts = []
        for index, button in enumerate(self.navigation):
            shortcut = QShortcut(QKeySequence(f'Ctrl+{index + 1}'), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda index=index: self._activate_page_shortcut(index))
            self.page_shortcuts.append(shortcut)
            button.setToolTip(f'{button.text()} · Ctrl+{index + 1}')
        self.primary_shortcuts = []
        for sequence in ('Ctrl+Return', 'Ctrl+Enter'):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(self._activate_primary_shortcut)
            self.primary_shortcuts.append(shortcut)
        self.apply_button.setToolTip('执行当前主操作 · Ctrl+Enter')
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

    def set_full_window_backdrop(self, enabled=True):
        self.full_window_backdrop = bool(enabled)
        if hasattr(self, 'material_shell') and self.material_shell is not None:
            self.material_shell.update()
        self._sync_sidebar_backdrop()

    def _backdrop_native_rect(self, full_window=None):
        """Map client area to physical desktop coordinates under all DPI scalings."""
        use_full = self.full_window_backdrop if full_window is None else bool(full_window)
        if not use_full:
            return self._sidebar_native_rect()
        from PySide6.QtWidgets import QApplication
        scale = 1.0
        origin_x = origin_y = 0
        phys_width = max(1, self.width())
        phys_height = max(1, self.height())
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
            scale = (rect.right - rect.left) / max(1, self.width())
            origin_x, origin_y = origin.x, origin.y
            phys_width = max(1, rect.right - rect.left)
            phys_height = max(1, rect.bottom - rect.top)
        else:
            phys_width = max(1, round(self.width() * scale))
            phys_height = max(1, round(self.height() * scale))
        return dict(x=origin_x, y=origin_y,
                    width=phys_width,
                    height=phys_height,
                    radius=0 if self.isMaximized() else round(20 * scale))

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
            state = dict(self._backdrop_native_rect(), sigma=self.sidebar_appearance.blur,
                         mode='full_window' if self.full_window_backdrop else 'sidebar',
                         visible=bool(self.blur_available and self.sidebar_transparent and self.material_active
                                      and self.isVisible() and not self.isMinimized() and self.sidebar_appearance.blur > 0))
        except OSError as error:
            self._backdrop_failed(str(error))
            host.close()
            return
        if state != self._last_backdrop_state:
            self._last_backdrop_state = state
            host.update(state)

    def _sync_backdrop(self):
        self._sync_sidebar_backdrop()

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
        previous_feedback = self.feedback
        self.feedback = FeedbackLabel(previous_feedback.text(), self)
        previous_feedback.hide()
        previous_feedback.deleteLater()
        notes.addWidget(self.draft_label)
        notes.addWidget(self.feedback)
        line.addWidget(summary, 1, Qt.AlignmentFlag.AlignVCenter)
        self.feedback_progress = QProgressBar()
        self.feedback_progress.setObjectName('materialOperationProgress')
        self.feedback_progress.setRange(0, 0)
        self.feedback_progress.setTextVisible(False)
        self.feedback_progress.setFixedSize(40, 4)
        self.feedback_progress.setAccessibleName('操作正在处理')
        self.feedback_progress.hide()
        line.addWidget(self.feedback_progress)
        self.feedback_details = QPushButton('查看详情')
        self.feedback_details.setObjectName('materialFeedbackDetails')
        self.feedback_details.setFixedSize(80, 38)
        self.feedback_details.setAccessibleName('查看完整操作说明、复制或重试')
        self.feedback_details.clicked.connect(self.show_feedback_details)
        self.feedback_details.hide()
        line.addWidget(self.feedback_details)
        self.feedback.text_changed.connect(self._sync_feedback_controls)
        self.discard.setText('取消')
        self.discard.setObjectName('materialCancel')
        self.discard.setAccessibleName('取消未应用的光标修改')
        self.discard.setFixedSize(64, 38)
        self.apply_button.setFixedSize(112, 38)
        line.addWidget(self.discard)
        line.addWidget(self.apply_button)

    def _sync_feedback_controls(self):
        if not hasattr(self, 'feedback_details'):
            return
        previous = getattr(self, '_failure_text', '')
        if previous and self.feedback.text() not in (previous, '') and not self.feedback.text().startswith('后台错误：'):
            self._failure_text = ''
            self._feedback_retry = None
            self._operation_retry = None
        self.feedback_details.setVisible(bool(self.feedback.text()) and
                                         (bool(self.feedback.property('error')) or self.feedback.is_elided()))
        self.feedback_progress.setVisible(self.busy)

    def _set_operation_feedback(self, text, *, error=False, retry=None, retry_text='重试'):
        self._failure_text = text if error else ''
        self._feedback_retry = retry
        self._feedback_retry_text = retry_text
        self.feedback.setProperty('error', error)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(text)
        self._sync_feedback_controls()

    def show_feedback_details(self):
        if self._feedback_dialog is not None and self._feedback_dialog.isVisible():
            self._feedback_dialog.raise_()
            return
        retry = self._feedback_retry if not self.busy else None
        dialog = FeedbackDetails(self, self.feedback.text(), approved_colors(self.ui_dark),
                                 self._feedback_retry_text if retry else '')
        self._feedback_dialog = dialog
        dialog.retry_action = retry
        if retry is not None:
            dialog.retry_requested.connect(self._retry_feedback)
        dialog.finished.connect(self._close_feedback_details)
        dialog.open()

    @Slot(int)
    def _close_feedback_details(self, result):
        dialog = self.sender()
        if self._feedback_dialog is dialog:
            self._feedback_dialog = None
        dialog.retry_action = None
        dialog.deleteLater()

    @Slot()
    def _retry_feedback(self):
        retry = self.sender().retry_action
        if retry is not None and not self.busy and retry is self._feedback_retry:
            self._commit_numeric_edit()
            retry()

    def _commit_numeric_edit(self):
        widget = QApplication.focusWidget()
        if widget is None or widget.window() is not self:
            return
        editor = widget
        while editor is not None and not isinstance(editor, QAbstractSpinBox):
            editor = editor.parentWidget()
        if editor is not None:
            editor.interpretText()
            editor.clearFocus()

    def _shortcut_allowed(self):
        return bool(self._material_ready and not self.busy and self.isActiveWindow()
                    and QApplication.activeModalWidget() is None
                    and QApplication.activePopupWidget() is None)

    def _activate_page_shortcut(self, index):
        if self._shortcut_allowed():
            self._commit_numeric_edit()
            self.select_page(index)

    def _activate_primary_shortcut(self):
        if self._shortcut_allowed():
            self._commit_numeric_edit()
            self._sync_material_actions()
            if self.apply_button.isEnabled():
                self.apply_draft()

    def _navigate_test_context(self, index):
        if self.busy:
            return
        self.select_page(index)
        if index == 3:
            button = self.pages[3].pause_btn
            self.stack.widget(3).ensureWidgetVisible(button, 0, 24)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _runtime_status_updated(self):
        if not self._material_ready:
            return
        self.pages[2].set_context(getattr(self, '_last_runtime_state', None),
                                 draft_dirty=self._draft != self.applied, busy=self.busy,
                                 error=getattr(self, '_last_runtime_error', ''))
        failure = getattr(self, '_failure_text', '')
        if failure and self.feedback.text().startswith('后台错误：'):
            self.feedback.setText(failure)
        self._sync_feedback_controls()

    def run_operation(self, operation, success, replace_draft=False):
        if self.busy:
            return
        cursor_apply = self._cursor_apply_requested
        self._operation_retry = self.apply_draft if cursor_apply else lambda: self.run_operation(operation, success, replace_draft)
        self._operation_cursor_apply = cursor_apply
        self._set_operation_feedback('正在处理，请稍候…')
        super().run_operation(operation, success, replace_draft)
        if cursor_apply and self._combined_apply_saved:
            self.feedback.setText('外观已保存；正在应用光标，请稍候…')
        self._runtime_status_updated()

    @Slot(object)
    def operation_done(self, result):
        if self._combined_apply_saved and self._operation_cursor_apply:
            self._operation_message = '外观已保存；光标配置已应用，效果已启动'
        self._combined_apply_saved = False
        self._failure_text = ''
        self._feedback_retry = None
        self._operation_retry = None
        super().operation_done(result)
        self._sync_feedback_controls()

    @Slot(str)
    def operation_failed(self, error):
        combined = self._combined_apply_saved and self._operation_cursor_apply
        self._combined_apply_saved = False
        super().operation_failed(error)
        if combined:
            message = f'外观已保存；光标应用失败：{error}。光标草稿已保留，可重试应用或取消草稿。'
        else:
            message = self.feedback.text()
        retry = self._operation_retry
        self._operation_retry = None
        label = '重试应用' if self._operation_cursor_apply else '重试操作'
        self._set_operation_feedback(message, error=True, retry=retry, retry_text=label)
        self._sync_material_actions()
        self._runtime_status_updated()

    def _apply_reference_theme(self):
        super()._apply_reference_theme()
        if not self._material_ready: return
        c=approved_colors(self.ui_dark)
        card_bg = 'rgba(255, 255, 255, 0.045)' if self.ui_dark else 'rgba(255, 255, 255, 0.65)'
        card_border = 'rgba(255, 255, 255, 0.09)' if self.ui_dark else 'rgba(0, 0, 0, 0.08)'
        card_top = 'rgba(255, 255, 255, 0.16)' if self.ui_dark else 'rgba(255, 255, 255, 0.90)'
        card_hover_bg = 'rgba(255, 255, 255, 0.065)' if self.ui_dark else 'rgba(255, 255, 255, 0.85)'
        card_hover_border = 'rgba(255, 255, 255, 0.16)' if self.ui_dark else 'rgba(0, 0, 0, 0.14)'
        card_hover_top = 'rgba(255, 255, 255, 0.26)' if self.ui_dark else 'rgba(255, 255, 255, 1.00)'
        self.setStyleSheet(self.styleSheet()+f"""
            QMainWindow, #materialWrapper, #materialShell, #materialContent, #content {{ background: transparent; }}
            #materialPageTitle, #materialWindowControls {{ background: transparent; border: none; }}
            #referenceSidebar {{ background: transparent; border: none; }}
            #navCapsule {{
                background: transparent;
                border: none;
                border-radius: 14px;
                padding: 4px;
                margin: 4px 8px;
            }}
            #navCapsule QPushButton {{
                border-radius: 10px;
                min-height: 36px;
                max-height: 42px;
                padding: 6px 14px;
                font-size: 13.5px;
                text-align: left;
                color: {'#b0b5c4' if self.ui_dark else '#515460'};
                border: 1px solid transparent;
            }}
            #navCapsule QPushButton:hover {{
                color: {c['text']};
                background: {'rgba(255, 255, 255, 0.08)' if self.ui_dark else 'rgba(0, 0, 0, 0.05)'};
                border: 1px solid {'rgba(255, 255, 255, 0.12)' if self.ui_dark else 'rgba(0, 0, 0, 0.06)'};
            }}
            #navCapsule QPushButton:checked {{
                color: #ffffff;
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(59, 130, 246, 0.82), stop:1 rgba(29, 78, 216, 0.88))' if self.ui_dark else 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0062d2, stop:1 #004ba4)'};
                border: 1px solid {'rgba(169, 206, 255, 0.45)' if self.ui_dark else '#0056b8'};
                border-top: 1px solid {'rgba(255, 255, 255, 0.65)' if self.ui_dark else 'rgba(255, 255, 255, 0.45)'};
                font-weight: 600;
            }}
            #navCapsule QPushButton:checked:hover {{
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(70, 145, 255, 0.88), stop:1 rgba(37, 99, 235, 0.94))' if self.ui_dark else 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a6ee8, stop:1 #0056b8)'};
                border-color: {'rgba(169, 206, 255, 0.65)' if self.ui_dark else '#0056b8'};
            }}
            #navCapsule QPushButton:pressed, #navCapsule QPushButton:checked:pressed {{
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(30, 64, 175, 0.90), stop:1 rgba(23, 37, 84, 0.95))' if self.ui_dark else '#003e82'};
                border-color: {'rgba(169, 206, 255, 0.35)' if self.ui_dark else '#003e82'};
                color: #ffffff;
            }}
            #navCapsule QPushButton[keyboardFocus="true"]:focus {{
                border: 2px solid {c['focus']};
            }}
            #approvedGroup, #referenceGroup, #referencePreview, QFrame#card {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-top: 1px solid {card_top};
                border-radius: 14px;
            }}
            #approvedGroup:hover, #referenceGroup:hover, #referencePreview:hover, QFrame#card:hover {{
                background-color: {card_hover_bg};
                border-color: {card_hover_border};
                border-top-color: {card_hover_top};
            }}
            #hairlineDivider {{ background: {'rgba(255, 255, 255, 0.06)' if self.ui_dark else 'rgba(0, 0, 0, 0.06)'}; border: none; }}
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
            QPushButton#materialFeedbackDetails {{ background: transparent; border: 1px solid {c['border']}; border-radius: 8px; color: {c['text']}; padding: 0; }}
            QPushButton#materialFeedbackDetails:hover {{ background: {c['raised']}; }}
            QPushButton#materialFeedbackDetails:focus {{ border-color: {c['focus']}; }}
            QProgressBar#materialOperationProgress {{ background: {c['raised']}; border: none; border-radius: 2px; }}
            QProgressBar#materialOperationProgress::chunk {{ background: {c['focus']}; border-radius: 2px; }}
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
        """ + scrollbar_style(self.ui_dark))
        self.material_shell.update()
        for button in self.title_bar.buttons.values():
            button.update()
        self._sync_sidebar_backdrop()

    def set_sidebar_transparent(self, enabled):
        self.sidebar_appearance = replace(self.sidebar_appearance, enabled=bool(enabled))
        self.sidebar_transparent = self._effective_transparency()
        self._refresh_sidebar_preview()

    def set_sidebar_transparency(self, value):
        key = 'dark_alpha' if self.ui_dark else 'light_alpha'
        self.sidebar_appearance = replace(self.sidebar_appearance, **{key: 255 - value})
        self._refresh_sidebar_preview()

    def cancel_sidebar_settings(self):
        self.sidebar_appearance = self.sidebar_saved
        self.sidebar_transparent = self._effective_transparency()
        self._refresh_sidebar_preview()

    def set_sidebar_blur(self, value):
        self.sidebar_appearance = replace(self.sidebar_appearance, blur=int(value))
        self.sidebar_transparent = self._effective_transparency()
        self._refresh_sidebar_preview()

    def _refresh_sidebar_preview(self):
        # Opacity and Gaussian radius change the material, not the widget theme.
        self.material_shell.update()
        self._sync_sidebar_backdrop()
        self.sidebar_controls.sync()
        self._sync_material_actions()

    def _sync_material_actions(self):
        cursor_dirty = self._draft != self.applied
        appearance_dirty = self.sidebar_dirty
        if appearance_dirty:
            self.draft_label.setText('外观待保存 · 光标待应用' if cursor_dirty else '外观待保存')
            self.apply_button.setText('保存并应用' if cursor_dirty else '保存外观')
        else:
            self.draft_label.setText('光标待应用' if cursor_dirty else '无待应用更改')
            retrying_apply = (cursor_dirty and self._feedback_retry is not None
                              and self._feedback_retry_text == '重试应用')
            self.apply_button.setText('重试应用' if retrying_apply else '应用更改')
        if self.busy:
            self.apply_button.setText('处理中…')
        pending = cursor_dirty or appearance_dirty
        drafts = (self._draft, self.sidebar_appearance)
        if (pending and drafts != getattr(self, '_feedback_drafts', drafts)
                and not self.busy and not self.feedback.property('error')):
            self.feedback.setText('')
        self._feedback_drafts = drafts
        color = ('#ffcf81' if self.ui_dark else '#9a4b00') if pending else approved_colors(self.ui_dark)['muted']
        style = f'color: {color}; font-weight: 600;'
        if self.draft_label.styleSheet() != style:
            self.draft_label.setStyleSheet(style)
        self.discard.setEnabled((cursor_dirty or appearance_dirty) and not self.busy)
        self.apply_button.setEnabled((cursor_dirty or (appearance_dirty and self.sidebar_store is not None))
            and not self.busy and not self.load_error and not self.pages[0].invalid_fields)
        self.discard.setAccessibleName('取消未保存的外观和未应用的光标修改')

    def discard_changes(self):
        self._failure_text = ''
        self._feedback_retry = None
        self._operation_retry = None
        if self._material_ready:
            self.cancel_sidebar_settings()
        super().discard_changes()

    def apply_draft(self):
        if self.busy:
            return
        self._commit_numeric_edit()
        if self.load_error or self.pages[0].invalid_fields:
            return
        cursor_dirty = self._draft != self.applied
        saved_appearance = self.sidebar_dirty
        if saved_appearance and not self.save_sidebar_settings():
            return
        self._combined_apply_saved = saved_appearance and cursor_dirty
        self._cursor_apply_requested = cursor_dirty
        try:
            super().apply_draft()
        finally:
            self._cursor_apply_requested = False

    def save_sidebar_settings(self):
        if self.busy:
            return False
        if self.sidebar_store is None:
            self.sidebar_controls.status.setText('此捕获窗口不保存外观，请使用安全预览入口。')
            return False
        try:
            self.sidebar_store.save(self.sidebar_appearance)
        except OSError as error:
            self.sidebar_controls.status.setText(f'外观保存失败：{error}。可重试或取消预览。')
            self._set_operation_feedback(f'外观保存失败：{error}。外观和光标草稿均已保留，可重试或取消。',
                                         error=True, retry=self.apply_draft, retry_text='重试保存')
            return False
        self.sidebar_saved = self.sidebar_appearance
        self.sync()
        self.sidebar_controls.status.setText('侧栏外观已保存，下次启动恢复。')
        self._set_operation_feedback('侧栏外观已保存')
        return True

    def closeEvent(self, event):
        if self.busy or self._threads:
            super().closeEvent(event)
            return
        if self.sidebar_dirty:
            message = '放弃未保存的侧栏外观和未应用的光标修改并关闭窗口？' if self._draft != self.applied else '放弃侧栏外观预览并关闭窗口？'
            if ask_confirmation(self, '未保存的修改', message, '放弃修改', '继续编辑') != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            event.accept()
            self._prewarm_closing = True
            self._prewarm_timer.stop()
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
        self._refresh_sidebar_preview()

    def nativeEvent(self, event_type, message):
        if self._material_ready and sys.platform == 'win32' and not self._policy_override:
            import ctypes
            from ctypes import wintypes
            native = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if native.message in (0x001A, 0x031A, 0x031E):
                QTimer.singleShot(0, self, self.refresh_material_policy)
            elif native.message in (0x0047, 0x02E0):
                QTimer.singleShot(0, self, self._sync_sidebar_backdrop)
        return super().nativeEvent(event_type, message)

    def sync(self):
        super().sync()
        if self._material_ready:
            self._sync_material_actions()
            self._fit_observation_height()
            self.sidebar_controls.sync()
            self._runtime_status_updated()

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
        if self._material_ready and watched is self.feedback and event.type() == QEvent.Type.Paint:
            self._sync_feedback_controls()
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
            self._refresh_sidebar_preview()
            QTimer.singleShot(0, self, self._start_sidebar_backdrop)

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
            self._refresh_sidebar_preview()
            for button in self.title_bar.buttons.values():
                button.update()
        if self._material_ready and event.type() == QEvent.Type.WindowStateChange:
            self._refresh_sidebar_preview()
            for button in self.title_bar.buttons.values():
                button.update()
        return super().event(event)
