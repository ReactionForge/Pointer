"""Value edits require an explicit choice; scrolling belongs to the page."""
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QSlider, QSpinBox, QDoubleSpinBox, QScrollArea


class PageWheelMixin:
    def wheelEvent(self, event):
        parent = self.parentWidget()
        while parent and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is None:
            event.ignore()
            return
        viewport = parent.viewport()
        local = event.globalPosition() - QPointF(viewport.mapToGlobal(QPoint()))
        forwarded = QWheelEvent(local, event.globalPosition(), event.pixelDelta(), event.angleDelta(),
                                event.buttons(), event.modifiers(), event.phase(), event.inverted(),
                                event.source() if hasattr(event, 'source') else Qt.MouseEventSource.MouseEventNotSynthesized,
                                event.pointingDevice())
        forwarded.setTimestamp(event.timestamp())
        # Route once to the containing page, never to another value widget.
        # Accept the original so native parent propagation cannot scroll twice.
        QApplication.sendEvent(viewport, forwarded)
        event.accept()


class ChoiceComboBox(PageWheelMixin, QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # The popup is its own window, so its viewport needs an explicit cursor.
        self.view().viewport().setCursor(Qt.CursorShape.PointingHandCursor)


class DragSlider(PageWheelMixin, QSlider):
    pass


class TypedSpinBox(PageWheelMixin, QSpinBox):
    pass


class TypedDoubleSpinBox(PageWheelMixin, QDoubleSpinBox):
    pass


class PropertyScrollArea(QScrollArea):
    def wheelEvent(self, event):
        pixels = event.pixelDelta()
        if not pixels.isNull():
            bar, delta = ((self.verticalScrollBar(), pixels.y()) if pixels.y()
                          else (self.horizontalScrollBar(), pixels.x()))
            before = bar.value()
            # Qt deltas already encode the user's natural-scroll direction.
            bar.setValue(before - delta)
            event.accept() if bar.value() != before else event.ignore()
            return
        super().wheelEvent(event)
