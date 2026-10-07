from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QPushButton, QLabel, QColorDialog, QFrame
)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QPen
from ..theme import card, SettingsRow, HairlineDivider
from ..input_controls import ChoiceComboBox, DragSlider


CORE_PRESETS = [
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

TRENDY_PRESETS = [
    {
        'id': 'cyber',
        'name': '赛博霓虹 Cyber',
        'desc': '赛博深紫与霓虹粉紫 · 极致炫彩',
        'light_body': '#12092b',
        'light_outline': '#ff007f',
        'dark_body': '#00f0ff',
        'dark_outline': '#7928ca',
    },
    {
        'id': 'mist',
        'name': '莫兰迪柔雾 Mist',
        'desc': '莫兰迪雾灰与北欧冷蓝 · 低饱和雅致',
        'light_body': '#3b4252',
        'light_outline': '#88c0d0',
        'dark_body': '#eceff4',
        'dark_outline': '#4c566a',
    },
    {
        'id': 'sakura',
        'name': '樱花浅粉 Sakura',
        'desc': '浅粉落樱与莓果暗红 · 温柔浪漫',
        'light_body': '#3c1b28',
        'light_outline': '#ff85a2',
        'dark_body': '#fff0f5',
        'dark_outline': '#f368e0',
    },
    {
        'id': 'abyssal',
        'name': '深海玄青 Abyssal',
        'desc': '幽邃海渊与清冽深青 · 浩瀚神秘',
        'light_body': '#071a2c',
        'light_outline': '#00b4d8',
        'dark_body': '#caf0f8',
        'dark_outline': '#03045e',
    },
]

PRESETS = CORE_PRESETS + TRENDY_PRESETS

# Keep legacy preset data unchanged for imported/saved user configurations.
WORKSPACE_PRESETS = [CORE_PRESETS[0],
    {'id': 'slate', 'name': '雾蓝', 'light_body': '#526575', 'light_outline': '#ffffff',
     'dark_body': '#bcc8d2', 'dark_outline': '#202124'},
    {'id': 'stone', 'name': '暖灰', 'light_body': '#6a625a', 'light_outline': '#ffffff',
     'dark_body': '#d8cfc3', 'dark_outline': '#202124'},
    {'id': 'sage', 'name': '鼠尾草', 'light_body': '#4f695d', 'light_outline': '#ffffff',
     'dark_body': '#bbcec2', 'dark_outline': '#202124'},
    {'id': 'clay', 'name': '陶土', 'light_body': '#855b4d', 'light_outline': '#ffffff',
     'dark_body': '#dfc2b4', 'dark_outline': '#202124'},
    {'id': 'mauve', 'name': '灰紫', 'light_body': '#70617c', 'light_outline': '#ffffff',
     'dark_body': '#cec2db', 'dark_outline': '#202124'},
    {'id': 'ocean', 'name': '深海', 'light_body': '#365c70', 'light_outline': '#ffffff',
     'dark_body': '#a9cbdc', 'dark_outline': '#202124'},
    {'id': 'rose', 'name': '烟粉', 'light_body': '#805d68', 'light_outline': '#ffffff',
     'dark_body': '#ddc2cc', 'dark_outline': '#202124'},
]


class AppearancePage(QWidget):
    """Grand cursor appearance workshop with live presets, styles, and custom dual-state palette."""
    def __init__(self, change):
        super().__init__()
        self.change, self.colors = change, {}
        self.settings = None
        self.preset_buttons = []
        self.trendy_preset_buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        def make_preset_button(preset):
            btn = QPushButton()
            btn.setObjectName('preset_' + preset['id'])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(48)
            btn.clicked.connect(lambda checked=False, p=preset: self.apply_preset(p))

            pixmap = QPixmap(38, 22)
            pixmap.fill(QColor('transparent'))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(preset['light_outline']), 1.4))
            painter.setBrush(QColor(preset['light_body']))
            painter.drawEllipse(1, 2, 17, 17)
            painter.setPen(QPen(QColor(preset['dark_outline']), 1.4))
            painter.setBrush(QColor(preset['dark_body']))
            painter.drawEllipse(19, 2, 17, 17)
            painter.end()

            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(38, 22))
            btn.setText(f"  {preset['name']}\n  {preset['desc']}")
            btn.setStyleSheet('''
                QPushButton {
                    text-align: left;
                    padding: 6px 12px;
                    background: rgba(255, 255, 255, 0.04);
                    border: 0.5px solid rgba(255, 255, 255, 0.09);
                    border-radius: 9px;
                    font-size: 11.5px;
                    color: #f5f5f7;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.08);
                    border-color: rgba(255, 255, 255, 0.18);
                    color: #ffffff;
                }
            ''')
            return btn

        # 1. Presets Showcase Gallery: Core 4 Presets
        preset_frame, preset_inner = card('经典调色方案', '内置 4 套经专业调校的高质感经典方案，高对比极简与暗金透亮。')
        preset_grid = QGridLayout()
        preset_grid.setSpacing(10)
        for index, preset in enumerate(CORE_PRESETS):
            btn = make_preset_button(preset)
            self.preset_buttons.append((btn, preset))
            preset_grid.addWidget(btn, index // 2, index % 2)
        preset_inner.addLayout(preset_grid)
        layout.addWidget(preset_frame)

        # 2. Trendy Presets Showcase Gallery: 4 Trendy Presets
        trendy_frame, trendy_inner = card('8 款潮流调色库 · 先锋视觉', '赛博朋克霓虹、北欧莫兰迪、浪漫粉樱与幽邃海渊，自由随心选用。')
        trendy_grid = QGridLayout()
        trendy_grid.setSpacing(10)
        for index, preset in enumerate(TRENDY_PRESETS):
            btn = make_preset_button(preset)
            self.trendy_preset_buttons.append((btn, preset))
            trendy_grid.addWidget(btn, index // 2, index % 2)
        trendy_inner.addLayout(trendy_grid)
        layout.addWidget(trendy_frame)

        # 3. Strategy, Shape, Size & Fine-tune Colors
        frame, inner = card('形态、微光与参数精调', '4 款几何形态发生器，依据背景亮度实时动态自适应，兼具呼吸微光与高分缩放。')

        # Geometric Style
        self.style = ChoiceComboBox()
        self.style.setObjectName('styleCombo')
        self.style.setMinimumWidth(260)
        for label, val in [
            ('经典圆角 (Sequoia Smooth · 经典圆润优雅)', 'sequoia'),
            ('精准十字 (Precision Studio · 设计师极简十字微尖标)', 'precision'),
            ('折角机甲 (Cyber Falcon · 凌厉切角机甲仿生线条)', 'falcon'),
            ('复古像素 (Pixel HD · 高清等比阶梯像素复古标)', 'pixel'),
        ]:
            self.style.addItem(label, val)
        self.style.currentIndexChanged.connect(lambda: change(style=self.style.currentData()))
        inner.addWidget(SettingsRow('几何形态发生器', '选择主箭头及全局指针几何轮廓造型发生器', self.style))

        inner.addWidget(HairlineDivider())

        # Appearance Strategy
        self.appearance = ChoiceComboBox()
        self.appearance.setObjectName('appearanceCombo')
        self.appearance.setMinimumWidth(260)
        for text, value in [
            ('自动适应背景 (推荐 · 依据底色明暗动态切换)', 'adaptive'),
            ('固定浅色背景方案 (锁定白底黑标)', 'light'),
            ('固定深色背景方案 (锁定深底亮标)', 'dark')
        ]:
            self.appearance.addItem(text, value)
        self.appearance.currentIndexChanged.connect(lambda: change(appearance=self.appearance.currentData()))
        inner.addWidget(SettingsRow('明暗自适应策略', '依据底层窗口背景明暗动态自适应或强制锁定', self.appearance))

        inner.addWidget(HairlineDivider())

        # Aura Glow
        from ..theme import MacSwitch
        self.aura_glow = MacSwitch()
        self.aura_glow.setObjectName('auraGlowSwitch')
        self.aura_glow.toggled.connect(lambda val: change(aura_glow=val))

        aura_container = QWidget()
        aura_layout = QHBoxLayout(aura_container)
        aura_layout.setContentsMargins(0, 0, 0, 0)
        aura_layout.setSpacing(10)
        aura_layout.addWidget(self.aura_glow)

        self.aura_color_btn = QPushButton("光晕色")
        self.aura_color_btn.setObjectName("auraColorBtn")
        self.aura_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.aura_color_btn.clicked.connect(self.pick_aura_color)
        aura_layout.addWidget(self.aura_color_btn)

        inner.addWidget(SettingsRow('外轮廓自适应呼吸微光 (Aura Glow)', '在指针外缘生成柔和通透的微光呼吸光晕，大幅强化杂乱界面的视觉聚焦', aura_container))

        inner.addWidget(HairlineDivider())

        # Size
        self.size = ChoiceComboBox()
        self.size.setObjectName('sizeCombo')
        self.size.setMinimumWidth(260)
        for size in (24, 32, 40, 48, 64):
            label = f'{size} px' + ('   (标准推荐 · 平衡适中)' if size == 32 else ('   (紧凑小屏 · 100% 缩放)' if size == 24 else '   (大屏清晰 · 高分显示)'))
            self.size.addItem(label, size)
        self.size.currentIndexChanged.connect(lambda: change(size=self.size.currentData()))
        inner.addWidget(SettingsRow('系统渲染尺寸', '矢量几何重绘，标准尺寸推荐 32px，支持 4K 缩放', self.size))

        inner.addWidget(HairlineDivider())

        colors_container = QHBoxLayout()
        colors_container.setSpacing(10)

        for theme, title, hint in [('light', '浅色背景状态', '浅底网页 / 白色文档'), ('dark', '深色背景状态', '暗黑系统 / 深色 IDE')]:
            col_box = QFrame()
            col_box.setStyleSheet('QFrame { background: rgba(255, 255, 255, 0.03); border: 0.5px solid rgba(255, 255, 255, 0.07); border-radius: 9px; padding: 6px 8px; }')
            col_layout = QVBoxLayout(col_box)
            col_layout.setContentsMargins(4, 4, 4, 4)
            col_layout.setSpacing(5)

            header_lbl = QLabel(f"<b>{title}</b>  <span style='color: #86868b; font-size: 11px;'>({hint})</span>")
            col_layout.addWidget(header_lbl)

            row = QHBoxLayout()
            row.setSpacing(6)
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

    def pick_aura_color(self):
        current_val = getattr(self.settings, 'aura_color', '#007aff') if self.settings else '#007aff'
        color = QColorDialog.getColor(QColor(current_val), self, '选择微光光晕颜色')
        if color.isValid():
            self.change(aura_color=color.name())

    def sync(self, settings):
        self.settings = settings
        for combo, value in [(self.appearance, settings.appearance), (self.size, settings.size)]:
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)

        if hasattr(self, 'style'):
            self.style.blockSignals(True)
            self.style.setCurrentIndex(self.style.findData(getattr(settings, 'style', 'sequoia')))
            self.style.blockSignals(False)

        if hasattr(self, 'aura_glow'):
            self.aura_glow.blockSignals(True)
            self.aura_glow.setChecked(getattr(settings, 'aura_glow', False))
            self.aura_glow.blockSignals(False)
            aura_c = getattr(settings, 'aura_color', '#007aff')
            self.aura_color_btn.setText(f"微光色 {aura_c.upper()}")

        # Update fine-tune buttons
        for field, (button, name) in self.colors.items():
            color = getattr(settings, field)
            button.setText(f"{name}  {color.upper()}")
            swatch = QPixmap(18, 18)
            swatch.fill(QColor('transparent'))
            painter = QPainter(swatch)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor('#86868b'), 1.2))
            painter.setBrush(QColor(color))
            painter.drawEllipse(1, 1, 15, 15)
            painter.end()
            button.setIcon(QIcon(swatch))
            button.setIconSize(QSize(18, 18))

        # Check if matches any preset
        all_buttons = self.preset_buttons + self.trendy_preset_buttons
        for btn, preset in all_buttons:
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
                        padding: 8px 14px;
                        background: rgba(0, 122, 255, 0.14);
                        border: 2px solid #007aff; /* 2px solid #2cb6ad */
                        border-radius: 10px;
                        font-size: 12px;
                        font-weight: 600;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background: rgba(0, 122, 255, 0.22);
                    }
                    QPushButton:pressed {
                        background: rgba(0, 122, 255, 0.3);
                    }
                ''')
            else:
                btn.setStyleSheet('''
                    QPushButton {
                        text-align: left;
                        padding: 8px 14px;
                        background: rgba(255, 255, 255, 0.04);
                        border: 0.5px solid rgba(255, 255, 255, 0.09);
                        border-radius: 10px;
                        font-size: 12px;
                        color: #f5f5f7;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.08);
                        border-color: rgba(255, 255, 255, 0.18);
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        background: rgba(255, 255, 255, 0.12);
                    }
                ''')

