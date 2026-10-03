from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox
from ..theme import card


class MotionPage(QWidget):
    def __init__(self, change):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        frame, inner = card('按下时的变化', '箭头整体向左下倾斜，下方两尖轻微跟随；松开后回到原位。')
        self.mode = QComboBox()
        for text, mode in [('整体倾斜','tilt'),('缩小回弹','shrink'),('关闭动效','off')]:
            self.mode.addItem(text,mode)
        self.mode.currentIndexChanged.connect(lambda: change(motion=self.mode.currentData()))
        inner.addWidget(self.mode)
        layout.addWidget(frame)
        frame, inner = card('动效节奏', '50% 强度延续现有造型。按下更轻快，松开更柔和。')
        self.sliders = {}
        for field, title, minimum, maximum, suffix in [('strength','动效强度',0,100,'%'),('press_ms','按下时间',40,200,' ms'),('release_ms','松开时间',80,400,' ms')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            row.addStretch()
            value = QLabel()
            row.addWidget(value)
            inner.addLayout(row)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum,maximum)
            slider.setObjectName({'strength':'strengthSlider','press_ms':'pressSlider','release_ms':'releaseSlider'}[field])
            slider.valueChanged.connect(lambda number, field=field: change(**{field:number}))
            inner.addWidget(slider)
            self.sliders[field] = (slider,value,suffix)
        layout.addWidget(frame)
        layout.addStretch()

    def sync(self, settings):
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData(settings.motion))
        self.mode.blockSignals(False)
        for field,(slider,label,suffix) in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(getattr(settings,field))
            slider.blockSignals(False)
            label.setText(str(getattr(settings,field))+suffix)
            slider.setEnabled(settings.motion != 'off')
