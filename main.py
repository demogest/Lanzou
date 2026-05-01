import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lanzou_downloader.models import DownloadTask
from lanzou_downloader.qt_worker import DownloadWorker
from mainWindow import Ui_MainWindow


class LanzouWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.threadpool = QThreadPool.globalInstance()
        self.active_worker = None

        self._modernize_ui()
        self.ui.DirText.setText(str(Path(os.getcwd()) / "Download"))
        self.ui.progressBar.setVisible(False)
        self.ui.DirBtn.clicked.connect(self.choose_directory)
        self.ui.StartBtn.clicked.connect(self.start_download)

    def _modernize_ui(self):
        self.setWindowTitle("Lanzou Downloader")
        self.resize(860, 660)
        self.setMinimumSize(780, 600)

        app_font = QFont("Microsoft YaHei UI", 11)
        if not app_font.exactMatch():
            app_font = QFont("Segoe UI", 11)
        self.setFont(app_font)

        for widget in (
            self.ui.LinkLab,
            self.ui.label_3,
            self.ui.DirLab,
            self.ui.LinkText,
            self.ui.PwdText,
            self.ui.DirText,
            self.ui.DirBtn,
            self.ui.StartBtn,
            self.ui.textBrowser,
            self.ui.progressBar,
        ):
            widget.setFont(app_font)

        self.ui.LinkLab.setText("分享链接")
        self.ui.label_3.setText("提取码")
        self.ui.DirLab.setText("保存位置")
        self.ui.LinkText.setPlaceholderText("粘贴蓝奏云分享链接")
        self.ui.PwdText.setPlaceholderText("没有提取码可留空")
        self.ui.DirText.setPlaceholderText("选择下载保存目录")
        self.ui.DirBtn.setText("选择目录")
        self.ui.StartBtn.setText("开始下载")

        self.ui.LinkText.setClearButtonEnabled(False)
        self.ui.PwdText.setClearButtonEnabled(False)
        self.ui.DirText.setClearButtonEnabled(False)
        self.ui.DirBtn.setIcon(QIcon())
        self.ui.StartBtn.setIcon(QIcon())

        for label in (self.ui.LinkLab, self.ui.label_3, self.ui.DirLab):
            label.setMinimumWidth(90)

        for separator in (self.ui.label, self.ui.label_2, self.ui.label_4):
            separator.hide()

        surface = QWidget(self)
        surface.setObjectName("AppSurface")
        for widget in (
            self.ui.LinkLab,
            self.ui.LinkText,
            self.ui.label_3,
            self.ui.PwdText,
            self.ui.DirLab,
            self.ui.DirText,
            self.ui.DirBtn,
            self.ui.StartBtn,
            self.ui.textBrowser,
            self.ui.progressBar,
        ):
            widget.setParent(surface)
        self.setCentralWidget(surface)

        shell = QVBoxLayout(surface)
        shell.setContentsMargins(40, 34, 40, 30)
        shell.setSpacing(10)

        title = QLabel("蓝奏云下载器", surface)
        title.setObjectName("TitleLabel")
        subtitle = QLabel("粘贴分享链接，选择保存目录，开始批量下载。", surface)
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        shell.addWidget(title)
        shell.addWidget(subtitle)
        shell.addSpacing(12)

        form_card = QFrame(surface)
        form_card.setObjectName("FormCard")
        form_card.setMinimumHeight(276)
        form_card.setMaximumHeight(286)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(24, 22, 24, 22)
        form_layout.setSpacing(12)

        def create_form_row(label, field):
            row = QWidget(form_card)
            row.setMinimumHeight(48)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(18)
            label.setFixedWidth(92)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_layout.addWidget(label)
            row_layout.addWidget(field, 1)
            return row

        directory_field = QWidget(form_card)
        directory_layout = QHBoxLayout(directory_field)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.setSpacing(12)
        directory_layout.addWidget(self.ui.DirText, 1)
        directory_layout.addWidget(self.ui.DirBtn)

        form_layout.addWidget(create_form_row(self.ui.LinkLab, self.ui.LinkText))
        form_layout.addWidget(create_form_row(self.ui.label_3, self.ui.PwdText))
        form_layout.addWidget(create_form_row(self.ui.DirLab, directory_field))

        action_widget = QWidget(form_card)
        action_widget.setMinimumHeight(48)
        action_row = QHBoxLayout(action_widget)
        action_row.setContentsMargins(0, 2, 0, 0)
        action_row.addStretch(1)
        action_row.addWidget(self.ui.StartBtn)
        form_layout.addWidget(action_widget)
        shell.addWidget(form_card)
        shell.addSpacing(18)

        log_card = QFrame(surface)
        log_card.setObjectName("LogCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(10)

        log_header = QLabel("运行日志", log_card)
        log_header.setObjectName("SectionLabel")
        self.ui.textBrowser.setParent(log_card)
        self.ui.progressBar.setParent(log_card)
        log_layout.addWidget(log_header)
        log_layout.addWidget(self.ui.textBrowser)
        log_layout.addWidget(self.ui.progressBar)
        shell.addWidget(log_card)
        shell.addStretch(1)

        self.ui.LinkText.setMinimumHeight(46)
        self.ui.PwdText.setMinimumHeight(46)
        self.ui.DirText.setMinimumHeight(46)
        self.ui.DirBtn.setMinimumHeight(46)
        self.ui.DirBtn.setMinimumWidth(128)
        self.ui.StartBtn.setMinimumHeight(46)
        self.ui.StartBtn.setMinimumWidth(156)
        self.ui.textBrowser.setPlaceholderText("等待任务开始...")
        self.ui.textBrowser.setFixedHeight(174)
        self.ui.textBrowser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ui.progressBar.setFixedHeight(10)

        self.setStyleSheet(
            """
            QWidget#AppSurface {
                background: #f6f8fb;
                color: #182230;
                font-family: "Microsoft YaHei UI", "Segoe UI";
            }
            QLabel#TitleLabel {
                color: #0b1220;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#SubtitleLabel {
                color: #64748b;
                font-size: 14px;
                font-weight: 500;
            }
            QLabel#SectionLabel {
                color: #1f2a44;
                font-size: 16px;
                font-weight: 700;
            }
            QFrame#FormCard {
                background: #ffffff;
                border: 1px solid #e1e7f0;
                border-radius: 8px;
            }
            QFrame#LogCard {
                background: #ffffff;
                border: 1px solid #e1e7f0;
                border-radius: 8px;
            }
            QLabel {
                color: #253858;
                font-size: 14px;
                font-weight: 600;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d2dce9;
                border-radius: 8px;
                color: #111827;
                font-size: 15px;
                padding: 9px 13px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
                background: #fbfdff;
            }
            QPushButton {
                background: #f8fafc;
                border: 1px solid #d2dce9;
                border-radius: 8px;
                color: #1f2a44;
                font-size: 15px;
                font-weight: 700;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background: #eef4fb;
            }
            QPushButton:pressed {
                background: #e2ebf6;
            }
            QPushButton:disabled {
                background: #edf1f6;
                border-color: #e1e7ef;
                color: #9aa6b2;
            }
            QPushButton#StartBtn {
                background: #2563eb;
                border: 1px solid #1d4ed8;
                color: #ffffff;
                font-size: 15px;
            }
            QPushButton#StartBtn:hover {
                background: #1d4ed8;
            }
            QPushButton#StartBtn:pressed {
                background: #1e40af;
            }
            QPushButton#StartBtn:disabled {
                background: #93b4f5;
                border-color: #93b4f5;
                color: #f8fbff;
            }
            QTextBrowser {
                background: #f8fafc;
                border: 1px solid #d7e0ec;
                border-radius: 8px;
                color: #344256;
                padding: 13px;
                font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
                font-size: 14px;
            }
            QProgressBar {
                background: #e8edf5;
                border: none;
                border-radius: 6px;
                color: #344054;
                font-weight: 700;
                height: 12px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #14b8a6;
                border-radius: 6px;
            }
            """
        )

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            self.ui.DirText.text(),
        )
        if directory:
            self.ui.DirText.setText(directory)

    def start_download(self):
        task = self._build_task()
        if task is None:
            return

        self._prepare_download_ui()
        worker = DownloadWorker(task)
        worker.signals.message.connect(self.append_message)
        worker.signals.progress.connect(self.ui.progressBar.setValue)
        worker.signals.error.connect(self.show_error)
        worker.signals.finished.connect(self.download_finished)
        self.active_worker = worker
        self.threadpool.start(worker)

    def _build_task(self):
        share_url = self.ui.LinkText.text().strip()
        if not share_url:
            self.append_message("Please input a share link.")
            return None

        target_dir = self.ui.DirText.text().strip()
        if not target_dir:
            target_dir = str(Path(os.getcwd()) / "Download")
            self.ui.DirText.setText(target_dir)

        return DownloadTask(
            share_url=share_url,
            password=self.ui.PwdText.text(),
            target_dir=Path(target_dir),
        )

    def _prepare_download_ui(self):
        self.ui.textBrowser.clear()
        self.ui.progressBar.setValue(0)
        self.ui.progressBar.setMinimum(0)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setTextVisible(True)
        self.ui.progressBar.setVisible(True)
        self.ui.StartBtn.setEnabled(False)
        self.ui.StartBtn.setText("下载中...")
        self.ui.DirBtn.setEnabled(False)

    def append_message(self, message):
        self.ui.textBrowser.append(message)

    def show_error(self, message):
        self.append_message("Error: %s" % message)

    def download_finished(self):
        self.ui.StartBtn.setEnabled(True)
        self.ui.StartBtn.setText("开始下载")
        self.ui.DirBtn.setEnabled(True)
        self.active_worker = None


def main():
    app = QApplication(sys.argv)
    window = LanzouWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
