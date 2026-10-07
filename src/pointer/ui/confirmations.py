"""Theme only Pointer-owned confirmation boxes; retain native file selectors."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMessageBox
from .colors import theme_colors


def confirmation_box(owner, title, message, proceed, keep='取消'):
    c = getattr(owner, 'confirmation_colors', theme_colors(bool(getattr(owner, 'ui_dark', False))))
    box = QMessageBox(owner)
    if hasattr(QMessageBox, 'Option'):
        box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Question)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(message)
    palette = QPalette(box.palette())
    roles = {'Window': 'canvas', 'WindowText': 'text', 'Base': 'surface', 'Text': 'text',
             'Button': 'raised', 'ButtonText': 'text', 'Highlight': 'selected', 'HighlightedText': 'selected_text'}
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for role, token in roles.items():
            palette.setColor(group, getattr(QPalette.ColorRole, role), QColor(c[token]))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
            if group == QPalette.ColorGroup.Disabled:
                palette.setColor(group, role, QColor(c['disabled_text']))
    box.setPalette(palette)
    box.setAutoFillBackground(True)
    box.setStyleSheet(f'''
        QMessageBox {{ background: {c['canvas']}; color: {c['text']}; }}
        QMessageBox QLabel {{ color: {c['text']}; background: transparent; font-size: 14px; }}
        QMessageBox QPushButton {{ background: {c['raised']}; color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 6px; padding: 6px 12px; min-height: 22px; }}
        QMessageBox QPushButton:hover {{ background: {c['surface']}; }}
        QMessageBox QPushButton:pressed {{ background: {c['pressed']}; color: white; }}
        QMessageBox QPushButton:focus {{ border: 2px solid {c['focus']}; }}
        QMessageBox QPushButton:disabled {{ background: {c['raised']}; color: {c['disabled_text']}; }}
        QMessageBox QPushButton#confirmationKeep {{ background: {c['selected']}; color: {c['selected_text']}; }}
        QMessageBox QPushButton#confirmationKeep:hover {{ border-color: {c['focus']}; }}
        QMessageBox QPushButton#confirmationKeep:pressed {{ background: {c['pressed']}; color: white; }}
        QMessageBox QPushButton#confirmationKeep:disabled {{ background: {c['raised']}; color: {c['disabled_text']}; }}
    ''')
    yes = box.addButton(QMessageBox.StandardButton.Yes)
    yes.setText(proceed)
    yes.setObjectName('confirmationProceed')
    no = box.addButton(QMessageBox.StandardButton.No)
    no.setText(keep)
    no.setObjectName('confirmationKeep')
    box.setDefaultButton(no)
    box.setEscapeButton(no)
    return box


def ask_confirmation(owner, title, message, proceed, keep='取消'):
    box = confirmation_box(owner, title, message, proceed, keep)
    result = box.exec()
    return QMessageBox.StandardButton.Yes if result == QMessageBox.StandardButton.Yes else QMessageBox.StandardButton.No
