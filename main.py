import json
import multiprocessing
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThreadPool, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from lanzou_downloader.models import DownloadTask
from lanzou_downloader.qt_worker import DownloadWorker
from mainWindow import Ui_MainWindow


SETTINGS_PATH = Path(__file__).with_name("lanzou_settings.json")
HISTORY_PATH = Path(__file__).with_name("lanzou_history.json")


class DownloadProgressDialog(QDialog):
    def __init__(self, parent=None, app_font=None):
        super().__init__(parent)
        self.setObjectName("DownloadDialog")
        self.setWindowTitle("下载进度")
        self.resize(760, 500)
        self.setMinimumSize(660, 420)
        if app_font is not None:
            self.setFont(app_font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("下载进度", self)
        title.setObjectName("DialogTitle")
        log_label = QLabel("运行日志", self)
        log_label.setObjectName("DialogSectionLabel")
        self.logBrowser = QTextBrowser(self)
        self.logBrowser.setPlaceholderText("等待任务开始...")

        self.currentProgressLabel = QLabel("当前文件", self)
        self.currentProgressLabel.setObjectName("DialogProgressLabel")
        self.currentProgressBar = QProgressBar(self)
        self.currentProgressBar.setObjectName("CurrentProgressBar")

        self.totalProgressLabel = QLabel("总进度", self)
        self.totalProgressLabel.setObjectName("DialogProgressLabel")
        self.totalProgressBar = QProgressBar(self)
        self.totalProgressBar.setObjectName("TotalProgressBar")

        for progress_bar in (self.currentProgressBar, self.totalProgressBar):
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setFixedHeight(24)
            if app_font is not None:
                progress_bar.setFont(app_font)

        layout.addWidget(title)
        layout.addWidget(log_label)
        layout.addWidget(self.logBrowser, 1)
        layout.addWidget(self.currentProgressLabel)
        layout.addWidget(self.currentProgressBar)
        layout.addWidget(self.totalProgressLabel)
        layout.addWidget(self.totalProgressBar)

        self.setStyleSheet(
            """
            QDialog#DownloadDialog {
                background: #f6f8fb;
                color: #182230;
                font-family: "Microsoft YaHei UI", "Segoe UI";
            }
            QLabel#DialogTitle {
                color: #0b1220;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#DialogSectionLabel {
                color: #1f2a44;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#DialogProgressLabel {
                color: #64748b;
                font-size: 13px;
                font-weight: 600;
            }
            QTextBrowser {
                background: #ffffff;
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
                border-radius: 8px;
                color: #344054;
                font-size: 13px;
                font-weight: 700;
                height: 24px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #14b8a6;
                border-radius: 8px;
            }
            QProgressBar#TotalProgressBar::chunk {
                background: #2563eb;
            }
            """
        )

    def reset(self):
        self.logBrowser.clear()
        self.currentProgressBar.setValue(0)
        self.totalProgressBar.setValue(0)

    def append_message(self, message):
        self.logBrowser.append(message)

    def mark_finished(self):
        self.setWindowTitle("下载完成")


class SettingsDialog(QDialog):
    def __init__(self, default_dir, process_count, on_choose_directory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载设置")
        self.resize(620, 240)
        self.setMinimumSize(560, 220)
        self._on_choose_directory = on_choose_directory
        self._max_processes = max(1, multiprocessing.cpu_count())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("设置", self)
        title.setObjectName("SectionLabel")
        hint = QLabel("可设置默认目录与下载进程（1 ~ CPU最大进程）。", self)
        hint.setObjectName("HintLabel")
        layout.addWidget(title)
        layout.addWidget(hint)

        self.defaultDirText = QLineEdit(self)
        self.defaultDirText.setText(default_dir)
        self.defaultDirBtn = QPushButton("选择目录", self)
        self.processCountSpin = QSpinBox(self)
        self.processCountSpin.setMinimum(1)
        self.processCountSpin.setMaximum(self._max_processes)
        self.processCountSpin.setValue(max(1, min(process_count, self._max_processes)))

        self.defaultDirBtn.clicked.connect(self.choose_default_directory)

        def row(label_text, field, extra=None):
            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            label = QLabel(label_text, row_widget)
            label.setFixedWidth(92)
            row_layout.addWidget(label)
            row_layout.addWidget(field, 1)
            if extra is not None:
                row_layout.addWidget(extra)
            return row_widget

        layout.addWidget(row("默认目录", self.defaultDirText, self.defaultDirBtn))
        layout.addWidget(row("下载进程", self.processCountSpin))

        action = QWidget(self)
        action_layout = QHBoxLayout(action)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addStretch(1)
        self.saveBtn = QPushButton("保存并关闭", self)
        self.saveBtn.clicked.connect(self.accept)
        action_layout.addWidget(self.saveBtn)
        layout.addWidget(action)

    def choose_default_directory(self):
        selected = self._on_choose_directory(self.defaultDirText.text().strip())
        if selected:
            self.defaultDirText.setText(selected)

    def values(self):
        default_dir = self.defaultDirText.text().strip()
        return default_dir, self.processCountSpin.value()


class LanzouWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.threadpool = QThreadPool.globalInstance()
        self.active_worker = None
        self.download_dialog = None
        self.default_download_dir, self.process_count = self._load_settings()
        self.last_task = None

        self._modernize_ui()
        self.ui.DirText.setText(self.default_download_dir)
        self.ui.DirBtn.clicked.connect(self.choose_directory)
        self.settingsBtn.clicked.connect(self.open_settings_dialog)
        self.historyBtn.clicked.connect(self.open_history_dialog)
        self.ui.StartBtn.clicked.connect(self.start_download)

    def _modernize_ui(self):
        self.setWindowTitle("Lanzou Downloader")
        self.resize(820, 610)
        self.setMinimumSize(720, 560)

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

        def create_form_row(label, field, parent):
            row = QWidget(parent)
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

        form_layout.addWidget(create_form_row(self.ui.LinkLab, self.ui.LinkText, form_card))
        form_layout.addWidget(create_form_row(self.ui.label_3, self.ui.PwdText, form_card))
        form_layout.addWidget(create_form_row(self.ui.DirLab, directory_field, form_card))

        action_widget = QWidget(form_card)
        action_widget.setMinimumHeight(48)
        action_row = QHBoxLayout(action_widget)
        action_row.setContentsMargins(0, 2, 0, 0)
        action_row.addStretch(1)
        action_row.addWidget(self.ui.StartBtn)
        form_layout.addWidget(action_widget)
        shell.addWidget(form_card)
        shell.addSpacing(16)
        bottom_action = QWidget(surface)
        bottom_layout = QHBoxLayout(bottom_action)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch(1)
        self.settingsBtn = QPushButton("下载设置", bottom_action)
        self.settingsBtn.setObjectName("SettingsBtn")
        self.settingsBtn.setMinimumHeight(42)
        self.settingsBtn.setMinimumWidth(128)
        bottom_layout.addWidget(self.settingsBtn)
        self.historyBtn = QPushButton("下载历史", bottom_action)
        self.historyBtn.setMinimumHeight(42)
        self.historyBtn.setMinimumWidth(128)
        bottom_layout.addWidget(self.historyBtn)
        shell.addWidget(bottom_action)
        shell.addStretch(1)

        self.ui.LinkText.setMinimumHeight(46)
        self.ui.PwdText.setMinimumHeight(46)
        self.ui.DirText.setMinimumHeight(46)
        self.ui.DirBtn.setMinimumHeight(46)
        self.ui.DirBtn.setMinimumWidth(128)
        self.ui.StartBtn.setMinimumHeight(46)
        self.ui.StartBtn.setMinimumWidth(156)

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
            QLabel#HintLabel {
                color: #64748b;
                font-size: 13px;
                font-weight: 500;
            }
            QFrame#FormCard {
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
            QPushButton#SettingsBtn {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1d4ed8;
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

    def choose_directory_dialog(self, current_dir):
        return QFileDialog.getExistingDirectory(
            self,
            "选择目录",
            current_dir.strip() or self.default_download_dir,
        )

    def open_settings_dialog(self):
        dialog = SettingsDialog(
            self.default_download_dir,
            self.process_count,
            self.choose_directory_dialog,
            self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        previous_default_dir = self.default_download_dir
        default_dir, process_count = dialog.values()
        if not default_dir:
            default_dir = self._fallback_download_dir()

        self.default_download_dir = default_dir
        self.process_count = process_count
        current_task_dir = self.ui.DirText.text().strip()
        if not current_task_dir or current_task_dir == previous_default_dir:
            self.ui.DirText.setText(default_dir)
        try:
            SETTINGS_PATH.write_text(
                json.dumps(
                    {
                        "default_download_dir": default_dir,
                        "process_count": process_count,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.warning(self, "设置保存失败", "无法保存设置：%s" % exc)
            return

        QMessageBox.information(self, "设置已保存", "默认目录和下载进程已更新。")

    def start_download(self):
        task = self._build_task()
        if task is None:
            return

        self.last_task = task
        self._prepare_download_ui()
        worker = DownloadWorker(task)
        worker.signals.message.connect(self.append_message)
        worker.signals.progress.connect(self.download_dialog.totalProgressBar.setValue)
        worker.signals.file_progress.connect(self.download_dialog.currentProgressBar.setValue)
        worker.signals.error.connect(self.show_error)
        worker.signals.finished.connect(self.download_finished)
        self.active_worker = worker
        self.threadpool.start(worker)

    def _build_task(self):
        share_url = self.ui.LinkText.text().strip()
        if not share_url:
            QMessageBox.warning(self, "缺少分享链接", "请先输入蓝奏云分享链接。")
            return None

        target_dir = self.ui.DirText.text().strip()
        if not target_dir:
            target_dir = self.default_download_dir
            self.ui.DirText.setText(target_dir)

        return DownloadTask(
            share_url=share_url,
            password=self.ui.PwdText.text(),
            target_dir=Path(target_dir),
            process_count=self.process_count,
        )

    def _prepare_download_ui(self):
        if self.download_dialog is not None:
            self.download_dialog.close()
        self.download_dialog = DownloadProgressDialog(self, self.font())
        self.download_dialog.reset()
        self.download_dialog.show()
        self.ui.StartBtn.setEnabled(False)
        self.ui.StartBtn.setText("下载中...")
        self.ui.DirBtn.setEnabled(False)

    def append_message(self, message):
        if self.download_dialog is not None:
            self.download_dialog.append_message(message)

    def show_error(self, message):
        self.append_message("Error: %s" % message)

    def download_finished(self, downloaded_paths):
        self.ui.StartBtn.setEnabled(True)
        self.ui.StartBtn.setText("开始下载")
        self.ui.DirBtn.setEnabled(True)
        if self.download_dialog is not None:
            self.download_dialog.mark_finished()
        self._append_history(downloaded_paths)
        self._prompt_open_folder(downloaded_paths)
        self.active_worker = None

    def _prompt_open_folder(self, downloaded_paths):
        folder = self.ui.DirText.text().strip() or self.default_download_dir
        message = QMessageBox(self)
        message.setWindowTitle("下载完成")
        message.setText("任务已完成，是否打开下载目录？")
        open_btn = message.addButton("打开文件夹", QMessageBox.AcceptRole)
        message.addButton("关闭", QMessageBox.RejectRole)
        message.exec_()
        if message.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _append_history(self, downloaded_paths):
        if self.last_task is None:
            return
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "share_url": self.last_task.share_url,
            "target_dir": str(self.last_task.target_dir),
            "process_count": self.last_task.process_count,
            "downloaded_count": len(downloaded_paths or []),
            "files": [str(path) for path in (downloaded_paths or [])],
        }
        history = self._load_history()
        history.insert(0, record)
        HISTORY_PATH.write_text(json.dumps(history[:200], ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_history(self):
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def open_history_dialog(self):
        history = self._load_history()
        dialog = QDialog(self)
        dialog.setWindowTitle("下载历史")
        dialog.resize(760, 480)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        if not history:
            browser.setText("暂无下载历史。")
        else:
            blocks = []
            for item in history:
                blocks.append(
                    "时间: {time}\n链接: {share_url}\n目录: {target_dir}\n进程: {process_count}\n下载文件数: {downloaded_count}\n".format(**item)
                )
            browser.setText("\n" + ("\n" + ("-" * 52) + "\n").join(blocks))
        layout.addWidget(browser)
        dialog.exec_()

    def _load_settings(self):
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._fallback_download_dir(), 1

        default_dir = str(settings.get("default_download_dir", "")).strip()
        process_count = int(settings.get("process_count", 1))
        process_count = max(1, min(process_count, max(1, multiprocessing.cpu_count())))
        return (default_dir or self._fallback_download_dir()), process_count

    def _fallback_download_dir(self):
        return str(Path(__file__).resolve().parent / "Download")


def main():
    app = QApplication(sys.argv)
    window = LanzouWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
