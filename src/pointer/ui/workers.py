from PySide6.QtCore import QObject, Signal, Slot


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self):
        try:
            self.finished.emit(self.operation())
        except Exception as error:
            self.failed.emit(str(error))
