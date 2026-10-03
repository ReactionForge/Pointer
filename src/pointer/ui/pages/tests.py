from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QSlider, QPlainTextEdit, QFrame
from ..theme import card


class TestSurface(QFrame):
    def __init__(self, page, name, role='arrow', dark=False):
        super().__init__()
        self.page, self.name, self.dragging = page, name, False
        self.setObjectName(name)
        self.setProperty('cursorRole', role)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(100)
        self.setStyleSheet('QFrame#'+name+' { background: '+('#202830' if dark else '#ffffff')+'; border: 1px solid #d6dfe6; border-radius: 8px; }')
        self.label = QLabel('深色区域' if dark else '浅色区域', self)
        self.label.move(14,13)
        self.label.setStyleSheet('color: '+('#cbd4dd' if dark else '#71808e')+'; background: transparent;')
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.page.down = True
            self.page.presses += 1
            self.page.update_counter()
            self.setFocus()
            if self.name == 'drag':
                self.dragging = True
                self.origin = event.position()
                self.label.setText('拖动中')
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position() - self.origin
            self.label.move(max(8,min(self.width()-110,14+int(delta.x()))),max(8,min(self.height()-30,13+int(delta.y()))))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_press()
        super().mouseReleaseEvent(event)

    def clear_press(self):
        self.page.down = False
        self.dragging = False
        self.page.update_counter()

    def event(self, event):
        if event.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate, QEvent.Type.UngrabMouse):
            self.clear_press()
        if event.type() in (QEvent.Type.Leave, QEvent.Type.Hide) and self.name == 'wait':
            self.page.set_wait(False)
        return super().event(event)


class TestPage(QWidget):
    def __init__(self, application):
        super().__init__()
        self.application, self.down, self.presses = application, False, 0
        self.surfaces = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        frame, inner = card('深浅背景适配', '移动真实鼠标跨过黑白交界，观察主体与边框切换。')
        row = QHBoxLayout()
        for name,dark in [('light-arrow',False),('dark-arrow',True)]:
            area = TestSurface(self,name,dark=dark)
            self.surfaces[name] = area
            row.addWidget(area)
        inner.addLayout(row)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0,255)
        self.brightness.setValue(128)
        inner.addWidget(self.brightness)
        self.gray = TestSurface(self,'brightness')
        self.gray.setMinimumHeight(62)
        inner.addWidget(self.gray)
        self.brightness.valueChanged.connect(self.set_brightness)
        self.set_brightness(128)
        shades = QHBoxLayout()
        for level in (0,48,96,144,192,255):
            block = QLabel(str(level))
            block.setAlignment(Qt.AlignmentFlag.AlignCenter)
            block.setMinimumHeight(36)
            block.setProperty('cursorRole','arrow')
            block.setStyleSheet(f'background: rgb({level},{level},{level}); color: '+('white' if level<128 else 'black')+'; border-radius: 3px;')
            shades.addWidget(block)
        inner.addLayout(shades)
        layout.addWidget(frame)
        frame, inner = card('左键、小手与拖动', '空白区域测试箭头；按住按钮测试小手；拖动卡片观察移动光标。')
        self.counter = QLabel()
        inner.addWidget(self.counter)
        row = QHBoxLayout()
        for dark in (False,True):
            button = QPushButton('按住测试小手')
            button.setProperty('cursorRole','hand')
            if dark:
                button.setStyleSheet('background: #202830; color: white; padding: 14px;')
            button.pressed.connect(self.button_press)
            button.released.connect(self.button_release)
            button.installEventFilter(self)
            row.addWidget(button)
        inner.addLayout(row)
        drag = TestSurface(self,'drag','move')
        drag.label.setText('拖动这张卡片')
        self.surfaces['drag'] = drag
        inner.addWidget(drag)
        layout.addWidget(frame)
        frame, inner = card('文字输入与加载', '加载效果只作用于下面的测试区域；离开区域即结束。')
        edit = QPlainTextEdit('在这里输入文字，检查 I 形光标。')
        edit.setProperty('cursorRole','ibeam')
        edit.viewport().setProperty('cursorRole','ibeam')
        edit.setMaximumHeight(95)
        inner.addWidget(edit)
        row = QHBoxLayout()
        for text,role in [('等待','busy'),('后台忙碌','working'),('结束加载','arrow')]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False,role=role:self.set_wait(role != 'arrow',role))
            row.addWidget(button)
        inner.addLayout(row)
        area = TestSurface(self,'wait')
        area.label.setText('点击上方按钮，再移动鼠标到这里')
        self.surfaces['wait'] = area
        inner.addWidget(area)
        layout.addWidget(frame)
        frame, inner = card('其他光标角色', '移动到每个区域，检查对应的系统光标。')
        grid = QGridLayout()
        for index,(text,role) in enumerate([('禁止','no'),('移动','move'),('水平缩放','ew'),('垂直缩放','ns'),('对角缩放 ↘','nwse'),('对角缩放 ↗','nesw'),('精确选择','crosshair'),('帮助','help'),('手写','pen'),('向上','up'),('位置','pin'),('人物','person')]):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setProperty('cursorRole',role)
            label.setMinimumHeight(54)
            label.setStyleSheet('background: #f3f5f7; border-radius: 5px;')
            grid.addWidget(label,index//3,index%3)
        inner.addLayout(grid)
        layout.addWidget(frame)
        self.update_counter()

    def scenario(self,name):
        return self.surfaces[name]

    def click_state(self):
        return {'down':self.down,'presses':self.presses}

    def update_counter(self):
        if hasattr(self,'counter'):
            self.counter.setText(f'左键：{"按下" if self.down else "松开"}    按下次数：{self.presses}')

    def button_press(self):
        self.down = True
        self.presses += 1
        self.update_counter()

    def button_release(self):
        self.down = False
        self.update_counter()

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.FocusOut,QEvent.Type.Hide,QEvent.Type.WindowDeactivate,QEvent.Type.UngrabMouse):
            self.button_release()
        return False

    def set_wait(self,enabled,role='busy'):
        if 'wait' in self.surfaces:
            area = self.surfaces['wait']
            area.setProperty('cursorRole',role if enabled else 'arrow')
            area.label.setText('加载测试进行中，离开这里即结束' if enabled else '点击上方按钮，再移动鼠标到这里')

    def finish_busy(self):
        self.set_wait(False)
        self.button_release()

    def set_brightness(self,value):
        self.gray.setStyleSheet(f'background: rgb({value},{value},{value}); border-radius: 8px;')
        self.gray.label.setText(f'亮度 {value} / 255')
        self.gray.label.setStyleSheet('color: '+('white' if value<128 else 'black')+'; background: transparent;')
