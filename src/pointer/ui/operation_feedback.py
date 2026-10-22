"""Readable, copyable operation feedback without growing the fixed action bar."""
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QSizePolicy, QVBoxLayout,
)


class FeedbackLabel(QLabel):
    """Keep the complete plain text while eliding only its painted summary."""
    text_changed = Signal()

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setObjectName('feedback')
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)

    def setText(self, text):
        changed = text != self.text()
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)
        if changed:
            self.text_changed.emit()

    def sizeHint(self):
        return QSize(0, self.fontMetrics().height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def is_elided(self):
        return ('\n' in self.text() or
                self.fontMetrics().horizontalAdvance(self.text()) > self.contentsRect().width())

    def paintEvent(self, event):
        painter = QPainter(self)
        summary = self.text().splitlines()[0] if self.text() else ''
        text = self.fontMetrics().elidedText(summary, Qt.TextElideMode.ElideRight,
                                            self.contentsRect().width())
        self.style().drawItemText(painter, self.contentsRect(),
                                 int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                                 self.palette(), self.isEnabled(), text, self.foregroundRole())


class FeedbackDetails(QDialog):
    """Window-owned full text, clipboard feedback and an explicit retry action."""
    retry_requested = Signal()

    def __init__(self, parent, text, colors, retry_text=''):
        super().__init__(parent)
        self.setObjectName('operationFeedbackDialog')
        self.setWindowTitle('操作详情')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(min(680, max(480, parent.width() - 80)),
                    min(400, max(280, parent.height() - 100)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        heading = QLabel('完整操作说明')
        heading.setObjectName('feedbackDetailHeading')
        layout.addWidget(heading)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setPlainText(text)
        self.body.setAccessibleName('完整操作说明，可选择文字')
        layout.addWidget(self.body, 1)
        actions = QHBoxLayout()
        self.copy_button = QPushButton('复制全文')
        self.copy_button.clicked.connect(self.copy_text)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        self.retry_button = QPushButton(retry_text or '重试')
        self.retry_button.setVisible(bool(retry_text))
        self.retry_button.clicked.connect(self.retry)
        actions.addWidget(self.retry_button)
        close = QPushButton('关闭')
        close.setDefault(True)
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.setStyleSheet(f'''
            QDialog#operationFeedbackDialog {{ background: {colors['canvas']}; color: {colors['text']}; }}
            #feedbackDetailHeading {{ color: {colors['text']}; font-size: 15px; font-weight: 600; }}
            QPlainTextEdit {{ background: {colors['surface']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 8px; padding: 10px; font-size: 13px; }}
            QPushButton {{ background: {colors['raised']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 8px; padding: 8px 14px; }}
            QPushButton:focus {{ border-color: {colors['focus']}; }}
        ''')

    def copy_text(self):
        QApplication.clipboard().setText(self.body.toPlainText())
        self.copy_button.setText('已复制全文')

    def retry(self):
        self.retry_requested.emit()
        self.accept()
