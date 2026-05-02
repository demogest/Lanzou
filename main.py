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
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QSplitter,
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
        self.resize(900, 560)
        self.setMinimumSize(780, 460)
        self._log_seq = 0
        self._process_rows = {}
        self._phase_labels = {"解析": "🔎", "下载": "⬇️", "完成": "✅", "错误": "❌"}
        if app_font is not None:
            self.setFont(app_font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("下载进度", self)
        title.setObjectName("DialogTitle")

        self.totalProgressLabel = QLabel("总进度", self)
        self.totalProgressLabel.setObjectName("DialogProgressLabel")
        self.totalProgressBar = QProgressBar(self)
        self.totalProgressBar.setObjectName("TotalProgressBar")

        self.totalProgressBar.setMinimum(0)
        self.totalProgressBar.setMaximum(100)
        self.totalProgressBar.setValue(0)
        self.totalProgressBar.setTextVisible(True)
        self.totalProgressBar.setFixedHeight(24)

        process_label = QLabel("进程子面板", self)
        process_label.setObjectName("DialogSectionLabel")

        self.processScroll = QScrollArea(self)
        self.processScroll.setObjectName("ProcessScroll")
        self.processScroll.setWidgetResizable(True)
        self.processScroll.setMinimumHeight(130)
        self.processScroll.setMaximumHeight(230)
        self.processPanel = QWidget(self.processScroll)
        self.processPanel.setObjectName("ProcessPanel")
        self.processLayout = QVBoxLayout(self.processPanel)
        self.processLayout.setContentsMargins(0, 0, 0, 0)
        self.processLayout.setSpacing(8)
        self.processScroll.setWidget(self.processPanel)

        self.logTree = QTreeWidget(self)
        self.logTree.setHeaderLabels(["阶段", "序号", "日志消息"])
        self.logTree.setRootIsDecorated(False)
        self.logTree.setAlternatingRowColors(True)
        self.logTree.header().setStretchLastSection(True)
        self.logTree.setColumnWidth(0, 88)
        self.logTree.setColumnWidth(1, 72)

        log_label = QLabel("多线程日志（按事件分行）", self)
        log_label.setObjectName("DialogSectionLabel")

        layout.addWidget(title)
        layout.addWidget(self.totalProgressLabel)
        layout.addWidget(self.totalProgressBar)
        layout.addWidget(process_label)
        layout.addWidget(self.processScroll)
        layout.addWidget(log_label)
        layout.addWidget(self.logTree, 1)

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
            QScrollArea#ProcessScroll {
                background: transparent;
                border: none;
            }
            QWidget#ProcessPanel {
                background: transparent;
            }
            QFrame#ProcessRow {
                background: #ffffff;
                border: 1px solid #d7e0ec;
                border-radius: 8px;
            }
            QLabel#ProcessSlotLabel {
                color: #1f2a44;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#ProcessFileLabel {
                color: #344256;
                font-size: 13px;
            }
            QLabel#ProcessStatusLabel {
                color: #64748b;
                font-size: 13px;
                font-weight: 700;
            }
            """
        )
        self.configure_processes(1)

    def reset(self, process_count=1):
        self.logTree.clear()
        self._log_seq = 0
        self.totalProgressBar.setValue(0)
        self.configure_processes(process_count)

    def configure_processes(self, process_count):
        process_count = max(1, int(process_count or 1))
        while self.processLayout.count():
            item = self.processLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._process_rows = {}
        for slot in range(1, process_count + 1):
            row = QFrame(self.processPanel)
            row.setObjectName("ProcessRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(10)

            slot_label = QLabel("进程 %d" % slot, row)
            slot_label.setObjectName("ProcessSlotLabel")
            slot_label.setFixedWidth(66)

            file_label = QLabel("等待任务", row)
            file_label.setObjectName("ProcessFileLabel")
            file_label.setMinimumWidth(160)
            file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            progress_bar = QProgressBar(row)
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setFixedHeight(22)

            status_label = QLabel("等待", row)
            status_label.setObjectName("ProcessStatusLabel")
            status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_label.setFixedWidth(66)

            row_layout.addWidget(slot_label)
            row_layout.addWidget(file_label, 2)
            row_layout.addWidget(progress_bar, 3)
            row_layout.addWidget(status_label)
            self.processLayout.addWidget(row)
            self._process_rows[slot] = {
                "file": file_label,
                "progress": progress_bar,
                "status": status_label,
            }
        self.processLayout.addStretch(1)

    def update_total_progress(self, progress):
        self.totalProgressBar.setValue(max(0, min(100, int(progress))))

    def update_process_progress(self, slot, file_name, progress, status):
        slot = int(slot or 1)
        row = self._process_rows.get(slot)
        if row is None:
            return
        display_name = file_name or "等待任务"
        display_status = status or "下载中"
        progress = max(0, min(100, int(progress)))
        row["file"].setText(display_name)
        row["file"].setToolTip(display_name if file_name else "")
        row["progress"].setValue(progress)
        row["status"].setText(display_status)

    def append_message(self, message):
        self._log_seq += 1
        msg = str(message).strip()
        phase = "下载"
        if "error" in msg.lower() or "失败" in msg:
            phase = "错误"
        elif "解析" in msg or "提取" in msg:
            phase = "解析"
        elif "完成" in msg:
            phase = "完成"
        icon = self._phase_labels.get(phase, "•")
        item = QTreeWidgetItem([f"{icon} {phase}", str(self._log_seq), msg])
        self.logTree.addTopLevelItem(item)
        self.logTree.scrollToItem(item)

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
            QSpinBox {
                background: #ffffff;
                border: 1px solid #d2dce9;
                border-radius: 8px;
                color: #111827;
                font-size: 15px;
                padding: 9px 13px;
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
        self._prepare_download_ui(task)
        worker = DownloadWorker(task)
        worker.signals.message.connect(self.append_message)
        worker.signals.progress.connect(self.download_dialog.update_total_progress)
        worker.signals.process_progress.connect(self.download_dialog.update_process_progress)
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

    def _prepare_download_ui(self, task):
        if self.download_dialog is not None:
            self.download_dialog.close()
        self.download_dialog = DownloadProgressDialog(self, self.font())
        self.download_dialog.reset(task.process_count)
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
        finished_time = datetime.now()
        file_records = []
        for file_path in (downloaded_paths or []):
            p = Path(file_path)
            size = "未知"
            try:
                if p.exists():
                    size = f"{p.stat().st_size / 1024:.1f} KB"
            except OSError:
                pass
            file_records.append({"name": p.name, "path": str(p), "size": size})

        record = {
            "time": finished_time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_time": finished_time.strftime("%Y-%m-%d %H:%M:%S"),
            "share_url": self.last_task.share_url,
            "password": self.last_task.password or "",
            "target_dir": str(self.last_task.target_dir),
            "process_count": self.last_task.process_count,
            "downloaded_count": len(downloaded_paths or []),
            "files": file_records,
        }
        history = self._load_history()
        history.insert(0, record)
        self._save_history(history[:200])

    def _load_history(self):
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _save_history(self, history):
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_history_dialog(self):
        history = self._load_history()
        dialog = QDialog(self)
        dialog.setWindowTitle("下载历史")
        dialog.resize(920, 540)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(dialog)
        list_panel = QWidget(splitter)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)

        history_list = QListWidget(list_panel)
        history_list.setAlternatingRowColors(True)

        action_bar = QWidget(list_panel)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        delete_btn = QPushButton("删除选中", action_bar)
        clear_btn = QPushButton("清空历史", action_bar)
        action_layout.addWidget(delete_btn)
        action_layout.addWidget(clear_btn)

        list_layout.addWidget(history_list, 1)
        list_layout.addWidget(action_bar)

        details = QTextBrowser(splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        def set_empty_state():
            history_list.clear()
            history_list.addItem("暂无下载历史")
            details.setText("暂无下载记录。")
            history_list.setEnabled(False)
            delete_btn.setEnabled(False)
            clear_btn.setEnabled(False)

        def populate_history_list():
            history_list.clear()
            for item in history:
                summary = f"{item.get('time', '-') }  |  {item.get('downloaded_count', 0)} 个文件  |  进程 {item.get('process_count', 1)}"
                row = QListWidgetItem(summary)
                row.setData(Qt.UserRole, item)
                history_list.addItem(row)
            history_list.setEnabled(True)
            delete_btn.setEnabled(True)
            clear_btn.setEnabled(True)

        def render_details(current_item):
            if current_item is None or not history:
                details.setText("暂无下载记录。")
                return
            record = current_item.data(Qt.UserRole) or {}
            file_lines = []
            for idx, f in enumerate(record.get("files", []), start=1):
                if isinstance(f, dict):
                    file_lines.append(f"{idx}. {f.get('name', '')} | {f.get('size', '未知')}\n    {f.get('path', '')}")
                else:
                    file_lines.append(f"{idx}. {f}")
            files_text = "\n".join(file_lines) if file_lines else "无"
            details.setText(
                "时间：{time}\n"
                "URL：{share_url}\n"
                "密码：{password}\n"
                "完成时间：{finished_time}\n"
                "保存目录：{target_dir}\n"
                "并发进程：{process_count}\n"
                "下载文件数：{downloaded_count}\n\n"
                "下载文件信息：\n{files}".format(
                    time=record.get("time", "-"),
                    share_url=record.get("share_url", "-"),
                    password=record.get("password") or "（无）",
                    finished_time=record.get("finished_time", record.get("time", "-")),
                    target_dir=record.get("target_dir", "-"),
                    process_count=record.get("process_count", 1),
                    downloaded_count=record.get("downloaded_count", 0),
                    files=files_text,
                )
            )

        def refresh_after_delete(next_row=0):
            if not history:
                set_empty_state()
                return
            populate_history_list()
            history_list.setCurrentRow(max(0, min(next_row, len(history) - 1)))

        def delete_selected_history():
            current_row = history_list.currentRow()
            if current_row < 0 or current_row >= len(history):
                return
            result = QMessageBox.question(
                dialog,
                "删除下载历史",
                "确定删除选中的下载历史吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                return
            history.pop(current_row)
            self._save_history(history)
            refresh_after_delete(current_row)

        def clear_history():
            if not history:
                return
            result = QMessageBox.question(
                dialog,
                "清空下载历史",
                "确定清空全部下载历史吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                return
            history.clear()
            self._save_history(history)
            set_empty_state()

        history_list.currentItemChanged.connect(lambda cur, _: render_details(cur))
        delete_btn.clicked.connect(delete_selected_history)
        clear_btn.clicked.connect(clear_history)
        if not history:
            set_empty_state()
        else:
            populate_history_list()
            history_list.setCurrentRow(0)

        layout.addWidget(splitter)
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
