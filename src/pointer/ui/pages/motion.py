from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QFrame, QPushButton
from ..theme import card, SettingsRow, HairlineDivider
from ..input_controls import ChoiceComboBox, DragSlider



class MotionPage(QWidget):
    """Motion Physics Lab: Tune click dynamics, spring dampening, and tactile curves."""
    def __init__(self, change):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        frame, inner = card('点击动效', '')
        self.mode = ChoiceComboBox()
        self.mode.setToolTip('选择整套光标的左键效果；应用后生效。')
        for text, mode in [('倾斜', 'tilt'), ('缩小回弹', 'shrink'),
                           ('弹簧回弹', 'spring'), ('关闭', 'off')]:
            self.mode.addItem(text, mode)
        self.mode.currentIndexChanged.connect(lambda: change(motion=self.mode.currentData()))

        inner.addWidget(self.mode)
        self.retired_hint = QLabel('')
        self.retired_hint.setObjectName('muted')
        self.retired_hint.setWordWrap(True)
        self.retired_hint.hide()
        inner.addWidget(self.retired_hint)
        layout.addWidget(frame)
        presets = QHBoxLayout()
        self.motion_recipes = []
        for title, fields in [('轻压', dict(motion='shrink', strength=20, press_ms=60, release_ms=120)),
                              ('轻倾', dict(motion='tilt', strength=25, press_ms=60, release_ms=150)),
                              ('静止', dict(motion='off'))]:
            button = QPushButton(title)
            button.setCheckable(True)
            self.motion_recipes.append((button, fields))
            button.setToolTip('设置当前动效草稿，显式应用后生效。')
            button.clicked.connect(lambda checked=False, fields=fields: change(**fields))
            presets.addWidget(button)
        layout.addLayout(presets)
        frame, inner = card('响应', '')
        self.sliders = {}

        specs = [
            ('strength', '强度', 0, 100, '%', 'strengthSlider', '调整位移、倾斜与缩放幅度。'),
            ('press_ms', '按下时间', 40, 200, ' ms', 'pressSlider', '值越小，按下响应越快。'),
            ('release_ms', '松开时间', 80, 400, ' ms', 'releaseSlider', '值越大，恢复越缓慢。'),
        ]

        for i, (field, title, minimum, maximum, suffix, obj_name, hint) in enumerate(specs):
            if i > 0:
                inner.addWidget(HairlineDivider())

            slider_widget = QWidget()
            sw_layout = QHBoxLayout(slider_widget)
            sw_layout.setContentsMargins(0, 0, 0, 0)
            sw_layout.setSpacing(12)

            slider = DragSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setObjectName(obj_name)
            slider.setMinimumWidth(80)
            slider.setAccessibleName(title)
            slider.setToolTip(hint)
            slider.valueChanged.connect(lambda number, field=field: change(**{field: number}))
            slider.sliderReleased.connect(lambda field=field, s=slider: change(_immediate=True, **{field: s.value()}))
            sw_layout.addWidget(slider, 1)

            value_lbl = QLabel()
            value_lbl.setStyleSheet('color: #007aff; font-weight: 600; font-size: 13px;')
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_lbl.setMinimumWidth(100)
            sw_layout.addWidget(value_lbl)

            title_label = QLabel(title)
            title_label.setToolTip(hint)
            inner.addWidget(title_label)
            inner.addWidget(slider_widget)
            self.sliders[field] = (slider, value_lbl, suffix)

        layout.addWidget(frame)
        layout.addStretch()

    def sync(self, settings):
        for button, fields in self.motion_recipes:
            button.setChecked(all(getattr(settings, field) == value for field, value in fields.items()))
        self.mode.blockSignals(True)
        for retired_mode in ('pulse', 'trail'):
            index = self.mode.findData(retired_mode)
            if index >= 0:
                self.mode.removeItem(index)
        retired = settings.motion in ('pulse', 'trail')
        if retired:
            self.mode.addItem('叠加动效已停用（配置保留）', settings.motion)
        self.mode.setCurrentIndex(self.mode.findData(settings.motion))
        self.mode.blockSignals(False)
        self.retired_hint.setText('此动效不再绘制；原配置保留。可选择倾斜、缩小回弹或关闭。')
        self.retired_hint.setVisible(retired)
        is_active = settings.motion not in ('off', 'pulse', 'trail')
        for field, (slider, label, suffix) in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(getattr(settings, field))
            slider.blockSignals(False)
            val = str(getattr(settings, field)) + suffix
            label.setText(val if is_active else f"{val} (未启用)")
            label.setStyleSheet('color: #007aff; font-weight: 600; font-size: 13px;' if is_active else 'color: #86868b; font-weight: 500; font-size: 13px;')
            slider.setEnabled(is_active)
