from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QFrame
from ..theme import card


class MotionPage(QWidget):
    def __init__(self, change):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Mode card
        frame, inner = card('点击反馈动效形式', '左键按下时给予细腻灵动的微物理反馈，松开后自然优雅回正。')
        self.mode = QComboBox()
        for text, mode in [
            ('📐  整体倾斜 (Tilt · 拟物灵动，箭头向左下自然倾侧受力)', 'tilt'),
            ('🎯  缩小回弹 (Shrink · 紧凑触感，微缩后柔和弹性复位)', 'shrink'),
            ('🚫  关闭动效 (Off · 纯静态指针，不触发形变)', 'off'),
        ]:
            self.mode.addItem(text, mode)
        self.mode.currentIndexChanged.connect(lambda: change(motion=self.mode.currentData()))
        inner.addWidget(self.mode)
        layout.addWidget(frame)

        # Rhythm & Parameters card
        frame, inner = card('动效节奏与物理手感', '精心调校的时间曲线与形变阻尼，按下敏捷利落，回弹自然丝滑。')
        self.sliders = {}

        specs = [
            (
                'strength', '动效形变强度', 0, 100, '%', 'strengthSlider',
                '控制位移与倾斜的最大幅度（推荐 40%–60%）'
            ),
            (
                'press_ms', '按下响应时间', 40, 200, ' ms', 'pressSlider',
                '鼠标左键压下时的形变过渡时间，更短越凌厉敏捷'
            ),
            (
                'release_ms', '松开回弹时间', 80, 400, ' ms', 'releaseSlider',
                '松开按键后平滑复位的缓冲时长，更长越柔和优雅'
            ),
        ]

        for field, title, minimum, maximum, suffix, obj_name, hint in specs:
            row_box = QFrame()
            row_box.setStyleSheet('QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px 12px; }')
            row_layout = QVBoxLayout(row_box)
            row_layout.setContentsMargins(8, 8, 8, 8)
            row_layout.setSpacing(6)

            header_row = QHBoxLayout()
            title_lbl = QLabel(f"<b>{title}</b>")
            header_row.addWidget(title_lbl)
            header_row.addStretch()

            value_lbl = QLabel()
            value_lbl.setStyleSheet('color: #207a75; font-weight: 600; font-size: 13px;')
            header_row.addWidget(value_lbl)
            row_layout.addLayout(header_row)

            hint_lbl = QLabel(hint)
            hint_lbl.setStyleSheet('color: #64748b; font-size: 11px;')
            row_layout.addWidget(hint_lbl)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setObjectName(obj_name)
            slider.valueChanged.connect(lambda number, field=field: change(**{field: number}))
            row_layout.addWidget(slider)

            inner.addWidget(row_box)
            self.sliders[field] = (slider, value_lbl, suffix)

        layout.addWidget(frame)
        layout.addStretch()

    def sync(self, settings):
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData(settings.motion))
        self.mode.blockSignals(False)
        is_active = (settings.motion != 'off')
        for field, (slider, label, suffix) in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(getattr(settings, field))
            slider.blockSignals(False)
            val = str(getattr(settings, field)) + suffix
            label.setText(val if is_active else f"{val} (未启用)")
            label.setStyleSheet('color: #207a75; font-weight: 600; font-size: 13px;' if is_active else 'color: #94a3b8; font-weight: 500; font-size: 13px;')
            slider.setEnabled(is_active)
