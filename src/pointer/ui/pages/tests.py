from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QBoxLayout,
    QLabel, QPushButton, QPlainTextEdit, QFrame, QTabBar, QSizePolicy
)
from ..theme import card
from ..colors import theme_colors
from ..parameter_controls import IntegerParameter


QT_CURSOR_MAP = {
    'arrow': Qt.CursorShape.ArrowCursor,
    'hand': Qt.CursorShape.PointingHandCursor,
    'ibeam': Qt.CursorShape.IBeamCursor,
    'help': Qt.CursorShape.WhatsThisCursor,
    'busy': Qt.CursorShape.WaitCursor,
    'working': Qt.CursorShape.BusyCursor,
    'move': Qt.CursorShape.SizeAllCursor,
    'ew': Qt.CursorShape.SizeHorCursor,
    'ns': Qt.CursorShape.SizeVerCursor,
    'nwse': Qt.CursorShape.SizeFDiagCursor,
    'nesw': Qt.CursorShape.SizeBDiagCursor,
    'crosshair': Qt.CursorShape.CrossCursor,
    'no': Qt.CursorShape.ForbiddenCursor,
    'pen': Qt.CursorShape.CrossCursor,
    'up': Qt.CursorShape.UpArrowCursor,
    'pin': Qt.CursorShape.PointingHandCursor,
    'person': Qt.CursorShape.ArrowCursor,
}


class TestSurface(QFrame):
    """High-contrast interactive test pad for tactile feel and native cursor transitions."""
    def __init__(self, page, name, role='arrow', dark=False):
        super().__init__()
        self.page, self.name, self.dragging = page, name, False
        self.setObjectName(name)
        self.setProperty('cursorRole', role)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(180)
        self.setMinimumHeight(104)

        bg = '#1c1c1e' if dark else '#f9f9fb'
        border = 'rgba(255, 255, 255, 0.08)' if dark else 'rgba(0, 0, 0, 0.08)'
        self.setStyleSheet(f'QFrame#{name} {{ background: {bg}; border: 1px solid {border}; border-radius: 10px; }}')

        self.label = QLabel('深色测试区域' if dark else '浅色测试区域', self)
        self.label.move(16, 14)
        text_color = '#f5f5f7' if dark else '#1d1d1f'
        self.label.setStyleSheet(f'color: {text_color}; background: transparent; font-weight: 600; font-size: 12px;')
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setWordWrap(True)
        self._fit_label()

    def set_label_text(self, text):
        self.label.setText(text)
        self._fit_label()

    def _fit_label(self):
        width = min(self.label.fontMetrics().horizontalAdvance(self.label.text()) + 16,
                    max(24, self.width() - 32))
        height = max(24, self.label.heightForWidth(width))
        self.label.resize(width, height)
        self.label.move(min(self.label.x(), max(16, self.width() - width - 16)),
                        min(self.label.y(), max(14, self.height() - height - 14)))

    def resizeEvent(self, event):
        self._fit_label()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.page.down = True
            self.page.presses += 1
            self.page.update_counter()
            self.setFocus()
            if self.name == 'drag':
                self.dragging = True
                self.origin = event.position()
                self.set_label_text('正在拖动卡片 (Move 游标)')
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position() - self.origin
            max_x = max(10, self.width() - self.label.width() - 10)
            max_y = max(10, self.height() - self.label.height() - 10)
            new_x = max(10, min(max_x, 16 + int(delta.x())))
            new_y = max(10, min(max_y, 14 + int(delta.y())))
            self.label.move(new_x, new_y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_press()
        super().mouseReleaseEvent(event)

    def clear_press(self):
        self.page.down = False
        self.dragging = False
        self.page.update_counter()
        if self.name == 'drag':
            self.set_label_text('拖动此卡片检验移动光标 (Move)')

    def event(self, event):
        if event.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate, QEvent.Type.UngrabMouse):
            self.clear_press()
        if event.type() in (QEvent.Type.Leave, QEvent.Type.Hide) and self.name == 'wait':
            self.page.set_wait(False)
        return super().event(event)


class TestPage(QWidget):
    """Local cursor checks grouped by the interaction being inspected."""
    def __init__(self, application):
        super().__init__()
        self.application, self.down, self.presses = application, False, 0
        self.surfaces = {}
        self.groups = []
        self.hand_buttons = []
        self.role_tiles = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.group_tabs = QTabBar()
        self.group_tabs.setObjectName('testGroups')
        self.group_tabs.setAccessibleName('光标测试分组')
        self.group_tabs.setExpanding(True)
        self.group_tabs.setDrawBase(False)
        self.group_tabs.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for title in ('背景适配', '点击与拖动', '输入与加载'):
            self.group_tabs.addTab(title)
        layout.addWidget(self.group_tabs)

        frame, inner = card('深浅背景与灰度', '移动鼠标跨过背景交界，检查已应用光标的主体与边框。')
        self.groups.append(frame)
        frame.setObjectName('testGroup')
        inner.setContentsMargins(16, 16, 16, 16)
        inner.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(12)
        for name, dark in [('light-arrow', False), ('dark-arrow', True)]:
            area = TestSurface(self, name, dark=dark)
            area.setMinimumHeight(144)
            self.surfaces[name] = area
            row.addWidget(area)
        inner.addLayout(row)

        gray_controls = QFrame()
        gray_controls.setObjectName('grayControls')
        slider_row = QHBoxLayout(gray_controls)
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setSpacing(12)
        sl_label = QLabel('灰度')
        sl_label.setObjectName('muted')
        slider_row.addWidget(sl_label)
        self.gray_parameter = IntegerParameter(0, 255, ' / 255', '测试背景灰度', '仅更改本页的测试背景。')
        self.brightness = self.gray_parameter.slider
        self.brightness_value = self.gray_parameter.editor
        self.gray_parameter.valueChanged.connect(self.set_brightness)
        slider_row.addWidget(self.gray_parameter, 1)
        self.gray_reset = QPushButton('重置')
        self.gray_reset.setObjectName('compactAction')
        self.gray_reset.setMinimumHeight(32)
        self.gray_reset.setAccessibleName('重置测试背景灰度为 128，不更改光标配置')
        self.gray_reset.setToolTip('恢复中间灰度 128，仅更改本页测试背景。')
        self.gray_reset.clicked.connect(lambda: self.set_brightness(128, force=True))
        slider_row.addWidget(self.gray_reset)
        inner.addWidget(gray_controls)

        self.gray = TestSurface(self, 'brightness')
        self.gray.setMinimumHeight(68)
        self.surfaces['brightness'] = self.gray
        inner.addWidget(self.gray)
        self.set_brightness(128)

        shades = QHBoxLayout()
        shades.setSpacing(6)
        for level in (0, 48, 96, 144, 192, 255):
            block = QLabel(f'{level}')
            block.setAlignment(Qt.AlignmentFlag.AlignCenter)
            block.setFixedHeight(28)
            block.setProperty('cursorRole', 'arrow')
            block.setStyleSheet(
                f'background: rgb({level},{level},{level}); '
                f'color: {"white" if level < 128 else "black"}; '
                f'border-radius: 6px; font-weight: 600; font-size: 11px;'
            )
            shades.addWidget(block)
        inner.addLayout(shades)
        layout.addWidget(frame)

        frame, inner = card('点击与拖动', '点击测试按下与松开；移入按钮检查手型，拖动下方文字检查移动光标。')
        self.groups.append(frame)
        frame.setObjectName('testGroup')
        inner.setContentsMargins(16, 16, 16, 16)
        inner.setSpacing(12)
        self.counter = QLabel()
        self.counter.setObjectName('testCounter')
        self.counter.setWordWrap(True)
        inner.addWidget(self.counter)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        for dark in (False, True):
            button = QPushButton('浅色测试区域 (手型)' if not dark else '深色测试区域 (手型)')
            button.setProperty('cursorRole', 'hand')
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if dark:
                button.setStyleSheet('background: #1c1c1e; color: #f5f5f7; border: 0.5px solid rgba(255, 255, 255, 0.1); padding: 11px; border-radius: 8px; font-weight: 600;')
            else:
                button.setStyleSheet('background: #f9f9fb; color: #1d1d1f; border: 0.5px solid rgba(0, 0, 0, 0.12); padding: 11px; border-radius: 8px; font-weight: 600;')
            button.pressed.connect(self.button_press)
            button.released.connect(self.button_release)
            button.installEventFilter(self)
            self.hand_buttons.append(button)
            btn_row.addWidget(button)
        inner.addLayout(btn_row)

        drag = TestSurface(self, 'drag', 'move')
        drag.setMinimumHeight(180)
        drag.set_label_text('拖动此卡片检验移动光标 (Move)')
        drag.setStyleSheet('QFrame#drag { background: rgba(0, 122, 255, 0.04); border: 1.5px dashed rgba(0, 122, 255, 0.35); border-radius: 10px; }')
        self.surfaces['drag'] = drag
        inner.addWidget(drag)
        layout.addWidget(frame)

        frame, inner = card('输入与加载', '输入文字检查文本光标；加载状态只在测试区域生效，移出或切换分组即结束。')
        self.groups.append(frame)
        frame.setObjectName('testGroup')
        inner.setContentsMargins(16, 16, 16, 16)
        inner.setSpacing(12)
        self.input_loading = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.input_loading.setSpacing(16)

        code_box = QFrame()
        code_box.setObjectName('testInput')
        code_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        code_layout = QVBoxLayout(code_box)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(8)

        code_title = QLabel('文本输入')
        code_title.setObjectName('testPanelTitle')
        code_layout.addWidget(code_title)

        edit = QPlainTextEdit(
            "// 在此处点击并输入文本，检验细腻的 I-Beam 光标\n"
            "const pointer = new Pointer({\n"
            "    theme: 'aurora-studio',\n"
            "    motion: 'tilt',\n"
            "    springStrength: 0.5\n"
            "});\n"
            "pointer.listen();"
        )
        self.editor = edit
        edit.setObjectName('testEditor')
        edit.setAccessibleName('文本光标输入测试')
        edit.setProperty('cursorRole', 'ibeam')
        edit.viewport().setProperty('cursorRole', 'ibeam')
        edit.setMinimumHeight(172)
        edit.setMaximumHeight(192)
        code_layout.addWidget(edit)
        self.input_loading.addWidget(code_box, 1)

        loading_box = QFrame()
        loading_box.setObjectName('testLoading')
        loading_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        loading_layout = QVBoxLayout(loading_box)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(8)
        load_title = QLabel('加载状态')
        load_title.setObjectName('testPanelTitle')
        loading_layout.addWidget(load_title)
        load_row = QHBoxLayout()
        load_row.setSpacing(6)
        for text, role in [('等待', 'busy'), ('后台运行', 'working'), ('结束加载', 'arrow')]:
            btn = QPushButton(text)
            btn.setObjectName('testLoadButton')
            btn.setMinimumHeight(32)
            btn.setAccessibleName(text + '光标测试')
            btn.clicked.connect(lambda checked=False, role=role: self.set_wait(role != 'arrow', role))
            load_row.addWidget(btn)
        loading_layout.addLayout(load_row)

        area = TestSurface(self, 'wait')
        area.set_label_text('点击上方按钮，再将鼠标移入此处观察加载动画')
        area.setStyleSheet('QFrame#wait { background: rgba(0, 122, 255, 0.06); border: 0.5px solid rgba(0, 122, 255, 0.3); border-radius: 10px; }')
        self.surfaces['wait'] = area
        area.setMinimumHeight(128)
        loading_layout.addWidget(area, 1)
        self.input_loading.addWidget(loading_box, 1)
        inner.addLayout(self.input_loading)

        inner.addSpacing(8)
        role_heading = QLabel('系统光标 · 17 种状态')
        role_heading.setObjectName('testPanelTitle')
        inner.addWidget(role_heading)
        self.role_grid = QGridLayout()
        self.role_grid.setSpacing(8)

        all_roles = [
            ('普通箭头', 'arrow', 'Arrow 默认指针'),
            ('链接手型', 'hand', 'Hand 悬浮指针'),
            ('文本选择', 'ibeam', 'IBeam 文字插入'),
            ('帮助选择', 'help', 'Help 问号指针'),
            ('等待沙漏', 'busy', 'Wait 忙碌等待'),
            ('后台运行', 'working', 'AppStarting 运行'),
            ('四向移动', 'move', 'SizeAll 拖拽移动'),
            ('水平缩放', 'ew', 'SizeWE 左右调整'),
            ('垂直缩放', 'ns', 'SizeNS 上下调整'),
            ('对角缩放 1', 'nwse', 'SizeNWSE 倾斜 1'),
            ('对角缩放 2', 'nesw', 'SizeNESW 倾斜 2'),
            ('精确十字', 'crosshair', 'Crosshair 定位'),
            ('禁止操作', 'no', 'No 无效操作'),
            ('手写输入', 'pen', 'NWPen 批注触控'),
            ('向上候选', 'up', 'UpArrow 坚立箭头'),
            ('位置定位', 'pin', 'Pin 空间图钉'),
            ('人物选择', 'person', 'Person 人员'),
        ]

        for index, (text, role, desc) in enumerate(all_roles):
            tile = QFrame()
            tile.setProperty('cursorRole', role)
            tile.setCursor(QT_CURSOR_MAP.get(role, Qt.CursorShape.ArrowCursor))
            tile.setMinimumHeight(52)
            tile.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            tile.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            tile.setAccessibleName(text + '，' + desc)
            tile.setObjectName('roleTile')
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(6, 6, 6, 6)
            tile_layout.setSpacing(2)

            t_lbl = QLabel(f"<b>{text}</b>")
            t_lbl.setProperty('cursorRole', role)
            t_lbl.setObjectName('tileTitle')
            t_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            d_lbl = QLabel(desc)
            d_lbl.setWordWrap(True)
            d_lbl.setProperty('cursorRole', role)
            d_lbl.setObjectName('tileSubtitle')
            d_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            tile_layout.addWidget(t_lbl)
            tile_layout.addWidget(d_lbl)
            self.role_tiles.append(tile)
            self.role_grid.addWidget(tile, index // 4, index % 4)

        inner.addLayout(self.role_grid)
        layout.addWidget(frame)
        layout.addStretch(1)

        self.group_tabs.currentChanged.connect(self.select_group)
        self.select_group(0)
        self._fit_groups()
        self.update_counter()
        self.set_theme(False)

    def set_theme(self, dark):
        colors = theme_colors(dark)
        self.gray_parameter.set_theme(dark)
        self.setStyleSheet(f'''
            QFrame#testGroup {{ background: {colors['surface']}; border: 1px solid {colors['divider']}; border-radius: 16px; }}
            QTabBar#testGroups {{ background: {colors['raised']}; border-radius: 10px; }}
            QTabBar#testGroups::tab {{ color: {colors['muted']}; background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 8px 12px; min-height: 20px; }}
            QTabBar#testGroups::tab:selected {{ background: {colors['surface']}; color: {colors['text']}; border-color: {colors['divider']}; }}
            QTabBar#testGroups::tab:hover {{ color: {colors['text']}; }}
            QTabBar#testGroups::tab:focus {{ border-color: {colors['focus']}; }}
            #grayControls, #testInput, #testLoading {{ background: transparent; border: none; }}
            #testCounter, #testValue {{ color: {colors['muted']}; background: transparent; border: none; font-size: 12px; }}
            #testPanelTitle {{ color: {colors['text']}; font-weight: 600; background: transparent; }}
            QPlainTextEdit#testEditor {{ background: {colors['canvas']}; color: {colors['text']}; font-family: Consolas, monospace; font-size: 12px; border: 1px solid {colors['divider']}; border-radius: 10px; padding: 10px; }}
            QPlainTextEdit#testEditor:focus {{ border-color: {colors['focus']}; }}
            QPushButton#testLoadButton {{ padding: 4px 8px; }}
            QFrame#roleTile {{ background: {colors['raised']}; border: 1px solid transparent; border-radius: 8px; }}
            QFrame#roleTile:focus {{ border-color: {colors['focus']}; }}
            #tileTitle {{ color: {colors['text']}; font-size: 12px; background: transparent; }}
            #tileSubtitle {{ color: {colors['muted']}; font-size: 11px; background: transparent; }}
        ''')
        for name in ('drag', 'wait'):
            surface = self.surfaces[name]
            surface.setStyleSheet(f"QFrame#{name} {{ background: {colors['raised']}; border: 1px {'dashed' if name == 'drag' else 'solid'} {colors['border']}; border-radius: 10px; }}")
            surface.label.setStyleSheet(f"color: {colors['text']}; background: transparent; font-weight: 600; font-size: 13px;")

    def select_group(self, index):
        self.finish_busy()
        for number, group in enumerate(self.groups):
            group.setVisible(number == index)
        self._fit_groups()

    def _fit_groups(self):
        if not hasattr(self, 'input_loading'):
            return
        wide = self.width() >= 760
        self.input_loading.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)
        columns = 4 if wide else 3 if self.width() >= 560 else 2
        for index, tile in enumerate(self.role_tiles):
            self.role_grid.removeWidget(tile)
            self.role_grid.addWidget(tile, index // columns, index % columns)

    def resizeEvent(self, event):
        self._fit_groups()
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.finish_busy()
        super().hideEvent(event)

    def scenario(self, name):
        return self.surfaces[name]

    def click_state(self):
        return {'down': self.down, 'presses': self.presses}

    def update_counter(self):
        if hasattr(self, 'counter'):
            state_text = '按下' if self.down else '已松开'
            self.counter.setText(f'{state_text}  ·  累计点击 {self.presses} 次')

    def button_press(self):
        self.down = True
        self.presses += 1
        self.update_counter()

    def button_release(self):
        self.down = False
        self.update_counter()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate, QEvent.Type.UngrabMouse):
            self.button_release()
        return False

    def set_wait(self, enabled, role='busy'):
        if 'wait' in self.surfaces:
            area = self.surfaces['wait']
            area.setProperty('cursorRole', role if enabled else 'arrow')
            area.set_label_text('加载动效测试进行中，移出该区域即自动结束' if enabled else '点击上方按钮，再将鼠标移入此处观察加载动画')

    def finish_busy(self):
        self.set_wait(False)
        self.button_release()
        for surface in self.surfaces.values():
            surface.clear_press()
        for button in self.hand_buttons:
            button.setDown(False)

    def set_brightness(self, value, force=False):
        self.gray_parameter.sync(value, force=force)
        self.gray.setStyleSheet(f'background: rgb({value},{value},{value}); border-radius: 9px;')
        self.gray.set_label_text(f'材质亮度 {value} / 255')
        self.gray.label.setStyleSheet('color: ' + ('white' if value < 128 else 'black') + '; background: transparent; font-weight: 600;')
