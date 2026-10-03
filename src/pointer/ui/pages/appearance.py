from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QPushButton, QLabel, QColorDialog, QFrame
)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QPen
from ..theme import card

PRESETS = [
    {
        'id': 'classic',
        'name': '经典自适应黑白',
        'desc': '纯净黑白 · 高对比经典极简',
        'light_body': '#000000',
        'light_outline': '#ffffff',
        'dark_body': '#ffffff',
        'dark_outline': '#000000',
    },
    {
        'id': 'aurora',
        'name': '极光冰蓝高亮',
        'desc': '青绿极光与冰蓝辉光 · 科技透亮',
        'light_body': '#0d273d',
        'light_outline': '#2cb6ad',
        'dark_body': '#e2fcfa',
        'dark_outline': '#15606d',
    },
    {
        'id': 'obsidian',
        'name': '曜石暖金',
        'desc': '黑曜深邃与轻奢暗金 · 沉稳温润',
        'light_body': '#211c18',
        'light_outline': '#e5b842',
        'dark_body': '#fffbf0',
        'dark_outline': '#8f6c1e',
    },
    {
        'id': 'geek',
        'name': '高对比极客',
        'desc': '深邃暗夜与荧光青翠 · 极限辨识',
        'light_body': '#0a0e14',
        'light_outline': '#00e575',
        'dark_body': '#00ff88',
        'dark_outline': '#0a0e14',
    },
]


class AppearancePage(QWidget):
    def __init__(self, change):
        super().__init__()
        self.change, self.colors = change, {}
        self.settings = None
        self.preset_buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 1. Presets Card
        preset_frame, preset_inner = card('精品配色预设', '内置 4 套精心校准的高质感配色方案，点击即可载入并自由微调。')
        preset_grid = QGridLayout()
        preset_grid.setSpacing(10)
        for index, preset in enumerate(PRESETS):
            btn = QPushButton()
            btn.setObjectName('preset_' + preset['id'])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(54)
            btn.clicked.connect(lambda checked=False, p=preset: self.apply_preset(p))

            # Render dual swatches icon
            pixmap = QPixmap(36, 20)
            pixmap.fill(QColor('transparent'))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Light swatch circle
            painter.setPen(QPen(QColor(preset['light_outline']), 1.5))
            painter.setBrush(QColor(preset['light_body']))
            painter.drawEllipse(1, 1, 16, 16)
            # Dark swatch circle
            painter.setPen(QPen(QColor(preset['dark_outline']), 1.5))
            painter.setBrush(QColor(preset['dark_body']))
            painter.drawEllipse(18, 1, 16, 16)
            painter.end()

            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(36, 20))
            btn.setText(f"  {preset['name']}\n  {preset['desc']}")
            btn.setStyleSheet('''
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 9px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #f0fdfa;
                    border-color: #2cb6ad;
                }
            ''')
            self.preset_buttons.append((btn, preset))
            preset_grid.addWidget(btn, index // 2, index % 2)
        preset_inner.addLayout(preset_grid)
        layout.addWidget(preset_frame)

        # 2. Strategy & Fine-tune Colors
        frame, inner = card('背景策略与自定义颜色', '自动适应鼠标所在底色的亮度，保留极致清晰的主体与外轮廓。')

        self.appearance = QComboBox()
        self.appearance.setObjectName('appearanceCombo')
        for text, value in [
            ('🌓  自动适应背景 (推荐 · 依据底色明暗动态切换)', 'adaptive'),
            ('☀️  固定浅色背景方案 (锁定白底黑标)', 'light'),
            ('🌙  固定深色背景方案 (锁定深底亮标)', 'dark')
        ]:
            self.appearance.addItem(text, value)
        self.appearance.currentIndexChanged.connect(lambda: change(appearance=self.appearance.currentData()))
        inner.addWidget(self.appearance)

        inner.addSpacing(6)
        colors_container = QHBoxLayout()
        colors_container.setSpacing(14)

        for theme, title, hint in [('light', '浅色背景状态', '用于浅底软件与网页'), ('dark', '深色背景状态', '用于深色主题与暗黑软件')]:
            col_box = QFrame()
            col_box.setStyleSheet('QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; }')
            col_layout = QVBoxLayout(col_box)
            col_layout.setContentsMargins(10, 8, 10, 8)
            col_layout.setSpacing(8)

            header_lbl = QLabel(f"<b>{title}</b>  <span style='color: #64748b; font-size: 11px;'>{hint}</span>")
            col_layout.addWidget(header_lbl)

            row = QHBoxLayout()
            row.setSpacing(8)
            for part, name in [('body', '主体颜色'), ('outline', '边框轮廓')]:
                field = f"{theme}_{part}"
                button = QPushButton()
                button.setObjectName(f"{field}Color")
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda checked=False, field=field: self.pick_color(field))
                self.colors[field] = (button, name)
                row.addWidget(button)
            col_layout.addLayout(row)
            colors_container.addWidget(col_box)

        inner.addLayout(colors_container)
        layout.addWidget(frame)

        # 3. Cursor Size
        frame, inner = card('光标尺寸', '尺寸随 Windows 显示缩放自适应渲染，高分辨率屏保持锐利边缘。')
        self.size = QComboBox()
        self.size.setObjectName('sizeCombo')
        for size in (24, 32, 40, 48, 64):
            label = f'{size} px' + ('   (标准默认)' if size == 32 else ('   (轻巧精巧)' if size == 24 else '   (大屏清晰)'))
            self.size.addItem(label, size)
        self.size.currentIndexChanged.connect(lambda: change(size=self.size.currentData()))
        inner.addWidget(self.size)
        layout.addWidget(frame)

        layout.addStretch()

    def apply_preset(self, preset):
        self.change(
            light_body=preset['light_body'],
            light_outline=preset['light_outline'],
            dark_body=preset['dark_body'],
            dark_outline=preset['dark_outline'],
        )

    def pick_color(self, field):
        current_val = getattr(self.settings, field) if self.settings else '#000000'
        color = QColorDialog.getColor(QColor(current_val), self, '选择光标颜色')
        if color.isValid():
            self.change(**{field: color.name()})

    def sync(self, settings):
        self.settings = settings
        for combo, value in [(self.appearance, settings.appearance), (self.size, settings.size)]:
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)

        # Update fine-tune buttons
        for field, (button, name) in self.colors.items():
            color = getattr(settings, field)
            button.setText(f"{name}  {color.upper()}")
            swatch = QPixmap(18, 18)
            swatch.fill(QColor('transparent'))
            painter = QPainter(swatch)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor('#94a3b8'))
            painter.setBrush(QColor(color))
            painter.drawEllipse(1, 1, 15, 15)
            painter.end()
            button.setIcon(QIcon(swatch))
            button.setIconSize(QSize(18, 18))

        # Check if matches any preset
        for btn, preset in self.preset_buttons:
            matches = (
                settings.light_body.casefold() == preset['light_body'].casefold() and
                settings.light_outline.casefold() == preset['light_outline'].casefold() and
                settings.dark_body.casefold() == preset['dark_body'].casefold() and
                settings.dark_outline.casefold() == preset['dark_outline'].casefold()
            )
            if matches:
                btn.setStyleSheet('''
                    QPushButton {
                        text-align: left;
                        padding: 8px 12px;
                        background: #f0fdfa;
                        border: 2px solid #2cb6ad;
                        border-radius: 9px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                ''')
            else:
                btn.setStyleSheet('''
                    QPushButton {
                        text-align: left;
                        padding: 8px 12px;
                        background: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-radius: 9px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background: #f0fdfa;
                        border-color: #2cb6ad;
                    }
                ''')
