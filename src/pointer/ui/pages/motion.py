from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QFrame
from ..theme import card, SettingsRow, HairlineDivider


class MotionPage(QWidget):
    """Motion Physics Lab: Tune click dynamics, spring dampening, and tactile curves."""
    def __init__(self, change):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 1. Mode card
        frame, inner = card('点击反馈动效微物理', '鼠标左键按下时给予富有生命力的微形变回弹，松开后自然优雅回正。')
        self.mode = QComboBox()
        self.mode.setMinimumWidth(260)
        for text, mode in [
            ('整体倾侧 (Tilt · 拟物灵动，受力自然微倾侧)', 'tilt'),
            ('缩小回弹 (Shrink · 紧凑触感，按压微缩后轻快回弹)', 'shrink'),
            ('关闭动效 (Off · 纯静态指针，保留纯净标准状态)', 'off'),
        ]:
            self.mode.addItem(text, mode)
        self.mode.currentIndexChanged.connect(lambda: change(motion=self.mode.currentData()))

        row_mode = SettingsRow('交互反馈模式', '模拟真实触控反馈物理惯性与微形变特征', self.mode)
        inner.addWidget(row_mode)
        layout.addWidget(frame)

        # 2. Rhythm & Parameters card
        frame, inner = card('物理手感与时间阻尼精调', '经真实操控手感验证的时间曲线与形变阻尼，按下敏捷利落，回弹自然丝滑。')
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

        for i, (field, title, minimum, maximum, suffix, obj_name, hint) in enumerate(specs):
            if i > 0:
                inner.addWidget(HairlineDivider())

            slider_widget = QWidget()
            sw_layout = QHBoxLayout(slider_widget)
            sw_layout.setContentsMargins(0, 0, 0, 0)
            sw_layout.setSpacing(12)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setObjectName(obj_name)
            slider.setMinimumWidth(160)
            slider.valueChanged.connect(lambda number, field=field: change(**{field: number}))
            slider.sliderReleased.connect(lambda field=field, s=slider: change(_immediate=True, **{field: s.value()}))
            sw_layout.addWidget(slider, 1)

            value_lbl = QLabel()
            value_lbl.setStyleSheet('color: #007aff; font-weight: 600; font-size: 13px;')
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_lbl.setFixedWidth(64)
            sw_layout.addWidget(value_lbl)

            row = SettingsRow(title, hint, slider_widget)
            inner.addWidget(row)
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
            label.setStyleSheet('color: #007aff; font-weight: 600; font-size: 13px;' if is_active else 'color: #86868b; font-weight: 500; font-size: 13px;')
            slider.setEnabled(is_active)
