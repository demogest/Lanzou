from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from .service import DownloadCallbacks, LanzouDownloadService


class DownloadSignals(QObject):
    message = pyqtSignal(str)
    progress = pyqtSignal(int)
    file_progress = pyqtSignal(int)
    process_progress = pyqtSignal(int, str, int, str)
    error = pyqtSignal(str)
    finished = pyqtSignal(object)


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
            on_process_progress=self.signals.process_progress.emit,
        )
        try:
            result = self.service.download(self.task, callbacks)
        except Exception as exc:
            self.signals.error.emit(str(exc))
            result = []
        finally:
            self.signals.finished.emit(result)
