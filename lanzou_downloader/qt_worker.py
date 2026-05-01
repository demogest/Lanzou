from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from .service import DownloadCallbacks, LanzouDownloadService


class DownloadSignals(QObject):
    message = pyqtSignal(str)
    progress = pyqtSignal(int)
    file_progress = pyqtSignal(int)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class DownloadWorker(QRunnable):
    def __init__(self, task, service=None):
        super().__init__()
        self.task = task
        self.service = service or LanzouDownloadService()
        self.signals = DownloadSignals()

    @pyqtSlot()
    def run(self):
        callbacks = DownloadCallbacks(
            on_message=self.signals.message.emit,
            on_progress=self.signals.progress.emit,
            on_file_progress=self.signals.file_progress.emit,
        )
        try:
            self.service.download(self.task, callbacks)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
