from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QPlainTextEdit, QFrame
)
from ..theme import card

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
        self.setMinimumHeight(104)

        bg = '#1c1c1e' if dark else '#f9f9fb'
        border = 'rgba(255, 255, 255, 0.08)' if dark else 'rgba(0, 0, 0, 0.08)'
        self.setStyleSheet(f'QFrame#{name} {{ background: {bg}; border: 1px solid {border}; border-radius: 10px; }}')

        self.label = QLabel('深色测试区域' if dark else '浅色测试区域', self)
        self.label.move(16, 14)
        text_color = '#f5f5f7' if dark else '#1d1d1f'
        self.label.setStyleSheet(f'color: {text_color}; background: transparent; font-weight: 600; font-size: 12px;')
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.adjustSize()

    def set_label_text(self, text):
        self.label.setText(text)
        self.label.adjustSize()

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
    """Panoramic Interactive Sandbox: Full-bleed arena with real Windows cursor validation."""
    def __init__(self, application):
        super().__init__()
        self.application, self.down, self.presses = application, False, 0
        self.surfaces = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 1. Real-world Contrast & Grayscale
        frame, inner = card('深浅背景跨界与灰度阶梯', '移动真实鼠标跨过黑白与灰度交界面，观察自适应光标主体与边框的高清平滑反转。')
        row = QHBoxLayout()
        row.setSpacing(12)
        for name, dark in [('light-arrow', False), ('dark-arrow', True)]:
            area = TestSurface(self, name, dark=dark)
            self.surfaces[name] = area
            row.addWidget(area)
        inner.addLayout(row)

        inner.addSpacing(4)
        slider_row = QHBoxLayout()
        sl_label = QLabel('动态连续灰度测试：')
        sl_label.setStyleSheet('color: #86868b; font-weight: 500; font-size: 12px;')
        slider_row.addWidget(sl_label)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 255)
        self.brightness.setValue(128)
        self.brightness.valueChanged.connect(self.set_brightness)
        slider_row.addWidget(self.brightness, 1)
        inner.addLayout(slider_row)

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
            block.setMinimumHeight(34)
            block.setProperty('cursorRole', 'arrow')
            block.setStyleSheet(
                f'background: rgb({level},{level},{level}); '
                f'color: {"white" if level < 128 else "black"}; '
                f'border-radius: 6px; font-weight: 600; font-size: 11px;'
            )
            shades.addWidget(block)
        inner.addLayout(shades)
        layout.addWidget(frame)

        # 2. Click, Hand & Dragging Playground
        frame, inner = card('左键动效、手型与拖动游标', '点击空白测试动效手感；悬浮或按住测试手型；拖拽卡片体验流畅移动光标。')
        self.counter = QLabel()
        self.counter.setStyleSheet('color: #007aff; background: rgba(0, 122, 255, 0.08); border: 0.5px solid rgba(0, 122, 255, 0.22); border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 12.5px;')
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
            btn_row.addWidget(button)
        inner.addLayout(btn_row)

        drag = TestSurface(self, 'drag', 'move')
        drag.set_label_text('拖动此卡片检验移动光标 (Move)')
        drag.setStyleSheet('QFrame#drag { background: rgba(0, 122, 255, 0.04); border: 1.5px dashed rgba(0, 122, 255, 0.35); border-radius: 10px; }')
        self.surfaces['drag'] = drag
        inner.addWidget(drag)
        layout.addWidget(frame)

        # 3. Real-world Code Editor & Busy Loading
        frame, inner = card('代码编辑与系统加载沙盒', '在富代码编辑区测试细腻的 I-Beam 文本输入光标；在加载区测试旋转动画。')

        # Code editor container
        code_box = QFrame()
        code_box.setStyleSheet('QFrame { background: #18181a; border: 0.5px solid rgba(255, 255, 255, 0.08); border-radius: 10px; }')
        code_layout = QVBoxLayout(code_box)
        code_layout.setContentsMargins(12, 10, 12, 10)
        code_layout.setSpacing(6)

        code_title = QLabel("<span style='color: #ff5f56;'>●</span> <span style='color: #ffbd2e;'>●</span> <span style='color: #27c93f;'>●</span>  <span style='color: #86868b; font-size: 11px; font-weight: 500;'>main.ts — Pointer Cursor Playground</span>")
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
        edit.setProperty('cursorRole', 'ibeam')
        edit.viewport().setProperty('cursorRole', 'ibeam')
        edit.setStyleSheet('''
            QPlainTextEdit {
                background: #121214;
                color: #f5f5f7;
                font-family: "SF Mono", Consolas, monospace;
                font-size: 12px;
                border: 0.5px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                padding: 10px;
            }
        ''')
        edit.setMaximumHeight(125)
        code_layout.addWidget(edit)
        inner.addWidget(code_box)

        # Wait state controls
        load_row = QHBoxLayout()
        load_row.setSpacing(10)
        for text, role in [('等待状态 (Wait)', 'busy'), ('后台运行 (AppStarting)', 'working'), ('结束加载', 'arrow')]:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked=False, role=role: self.set_wait(role != 'arrow', role))
            load_row.addWidget(btn)
        inner.addLayout(load_row)

        area = TestSurface(self, 'wait')
        area.set_label_text('点击上方按钮，再将鼠标移入此处观察加载动画')
        area.setStyleSheet('QFrame#wait { background: rgba(0, 122, 255, 0.06); border: 0.5px solid rgba(0, 122, 255, 0.3); border-radius: 10px; }')
        self.surfaces['wait'] = area
        inner.addWidget(area)
        layout.addWidget(frame)

        # 4. All 17 System Cursor Roles Matrix
        frame, inner = card('全部 17 种 Windows 系统光标矩阵', '移动鼠标至各个卡片，即刻调用对应原生系统光标进行实时检验。')
        grid = QGridLayout()
        grid.setSpacing(10)

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
            tile.setMinimumHeight(56)
            tile.setStyleSheet('''
                QFrame {
                    background: rgba(255, 255, 255, 0.035);
                    border: 0.5px solid rgba(255, 255, 255, 0.07);
                    border-radius: 8px;
                    padding: 6px 10px;
                }
                QFrame:hover {
                    background: rgba(0, 122, 255, 0.12);
                    border-color: rgba(0, 122, 255, 0.35);
                }
            ''')
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(6, 6, 6, 6)
            tile_layout.setSpacing(2)

            t_lbl = QLabel(f"<b>{text}</b>")
            t_lbl.setProperty('cursorRole', role)
            t_lbl.setStyleSheet('color: #f5f5f7; font-size: 12px;')
            t_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            d_lbl = QLabel(desc)
            d_lbl.setProperty('cursorRole', role)
            d_lbl.setStyleSheet('color: #86868b; font-size: 11px;')
            d_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            tile_layout.addWidget(t_lbl)
            tile_layout.addWidget(d_lbl)
            grid.addWidget(tile, index // 3, index % 3)

        inner.addLayout(grid)
        layout.addWidget(frame)

        self.update_counter()

    def scenario(self, name):
        return self.surfaces[name]

    def click_state(self):
        return {'down': self.down, 'presses': self.presses}

    def update_counter(self):
        if hasattr(self, 'counter'):
            state_text = '● 按下' if self.down else '○ 松开'
            self.counter.setText(f'鼠标手感监测：当前状态 {state_text}    |    累计点击次数：{self.presses} 次')

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

    def set_brightness(self, value):
        self.gray.setStyleSheet(f'background: rgb({value},{value},{value}); border-radius: 9px;')
        self.gray.set_label_text(f'材质亮度 {value} / 255')
        self.gray.label.setStyleSheet('color: ' + ('white' if value < 128 else 'black') + '; background: transparent; font-weight: 600;')
