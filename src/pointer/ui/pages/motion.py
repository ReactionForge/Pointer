from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from pointer.cursor.settings import CursorSettings
from ..theme import card, HairlineDivider
from ..input_controls import ChoiceComboBox
from ..parameter_controls import IntegerParameter

class MotionPage(QWidget):
    """Motion Physics Lab: Tune click dynamics, spring dampening, and tactile curves."""
    def __init__(self, change):
        super().__init__()
        self._change = change
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        frame, inner = card('点击动效', '')
        heading = QHBoxLayout()
        heading.addWidget(inner.takeAt(0).widget(), 1)
        self.reset_motion = QPushButton('重置')
        self.reset_motion.setObjectName('compactAction')
        self.reset_motion.setMinimumHeight(32)
        self.reset_motion.setAccessibleName('重置动效草稿为默认模式、强度和时间')
        self.reset_motion.setToolTip('恢复默认动效、强度与时间；应用后生效。')
        self.reset_motion.clicked.connect(self._reset_motion)
        heading.addWidget(self.reset_motion)
        inner.insertLayout(0, heading)
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
        self.editors = {}
        self.parameters = {}

        specs = [
            ('strength', '强度', 0, 100, '%', 'strengthSlider', '调整位移、倾斜与缩放幅度。'),
            ('press_ms', '按下时间', 40, 200, ' ms', 'pressSlider', '值越小，按下响应越快。'),
            ('release_ms', '松开时间', 80, 400, ' ms', 'releaseSlider', '值越大，恢复越缓慢。'),
        ]

        for i, (field, title, minimum, maximum, suffix, obj_name, hint) in enumerate(specs):
            if i > 0:
                inner.addWidget(HairlineDivider())

            parameter = IntegerParameter(minimum, maximum, suffix, title, hint)
            parameter.slider.setObjectName(obj_name)
            parameter.valueChanged.connect(lambda number, field=field: change(**{field: number}))
            parameter.committed.connect(lambda number, field=field: change(_immediate=True, **{field: number}))

            title_label = QLabel(title)
            title_label.setToolTip(hint)
            inner.addWidget(title_label)
            inner.addWidget(parameter)
            self.parameters[field] = parameter
            self.editors[field] = parameter.editor
            self.sliders[field] = (parameter.slider, parameter.editor, suffix)

        layout.addWidget(frame)
        layout.addStretch()

    def _reset_motion(self):
        defaults = CursorSettings()
        fields = {field: getattr(defaults, field)
                  for field in ('motion', 'strength', 'press_ms', 'release_ms')}
        for field, parameter in self.parameters.items():
            parameter.sync(fields[field], force=True)
        self._change(**fields)

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
        dark = bool(getattr(self.window(), 'ui_dark', False))
        for field, parameter in self.parameters.items():
            parameter.sync(getattr(settings, field), active=is_active)
            parameter.set_theme(dark)
