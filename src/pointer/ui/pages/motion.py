from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QFrame
from ..theme import card


class MotionPage(QWidget):
    """Motion Physics Lab: Tune click dynamics, spring dampening, and tactile curves."""
    def __init__(self, change):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Mode card
        frame, inner = card('⚡ 点击反馈动效微物理', '鼠标左键按下时给予富有生命力的微形变回弹，松开后自然优雅回正。')
        self.mode = QComboBox()
        for text, mode in [
            ('📐  整体倾斜 (Tilt · 拟物灵动，箭头受力自然向左下倾侧)', 'tilt'),
            ('🎯  缩小回弹 (Shrink · 紧凑触感，按压微缩后轻快回弹)', 'shrink'),
            ('🚫  关闭动效 (Off · 纯静态指针，保留纯净标准状态)', 'off'),
        ]:
            self.mode.addItem(text, mode)
        self.mode.currentIndexChanged.connect(lambda: change(motion=self.mode.currentData()))
        inner.addWidget(self.mode)
        layout.addWidget(frame)

        # Rhythm & Parameters card
        frame, inner = card('⏱ 物理手感与时间阻尼精调', '经真实操控手感验证的时间曲线与形变阻尼，按下敏捷利落，回弹自然丝滑。')
        self.sliders = {}

        specs = [
            (
                'strength', '动效形变强度', 0, 100, '%', 'strengthSlider',
                '控制位移与倾斜的最大幅度（推荐 40%–60% 适度微反馈）'
            ),
            (
                'press_ms', '按下响应时间', 40, 200, ' ms', 'pressSlider',
                '左键压下时的形变过渡时长，数值越小越敏捷锐利'
            ),
            (
                'release_ms', '松开回弹时间', 80, 400, ' ms', 'releaseSlider',
                '松开按键后平滑复位的缓冲时长，数值越大越柔和优雅'
            ),
        ]

        for field, title, minimum, maximum, suffix, obj_name, hint in specs:
            row_box = QFrame()
            row_box.setStyleSheet('QFrame { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 11px; padding: 10px 14px; }')
            row_layout = QVBoxLayout(row_box)
            row_layout.setContentsMargins(8, 8, 8, 8)
            row_layout.setSpacing(6)

            header_row = QHBoxLayout()
            title_lbl = QLabel(f"<b>{title}</b>")
            title_lbl.setStyleSheet('color: #f1f5f9; font-size: 13px;')
            header_row.addWidget(title_lbl)
            header_row.addStretch()

            value_lbl = QLabel()
            value_lbl.setStyleSheet('color: #2cb6ad; font-weight: 700; font-size: 13px;')
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
            label.setStyleSheet('color: #2cb6ad; font-weight: 700; font-size: 13px;' if is_active else 'color: #64748b; font-weight: 500; font-size: 13px;')
            slider.setEnabled(is_active)
