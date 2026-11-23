import os
import shutil
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.page_action import re_run_actions, record_page_actions

from .action_list_widget import ActionListWidget
from .playback_widget import PlaybackWidget


class RecordWorker(QThread):
    finished_recording = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.stop_event = threading.Event()

    def run(self):
        try:
            actions = record_page_actions(self.url, self.stop_event)
            self.finished_recording.emit(actions)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.stop_event.set()


class ReRunWorker(QThread):
    status_changed = Signal(str)
    finished_rerun = Signal(str, object, float)
    error_occurred = Signal(str)

    def __init__(self, url: str, actions: list[dict]):
        super().__init__()
        self.url = url
        self.actions = actions
        self.stop_event = threading.Event()

    def run(self):
        try:
            result = re_run_actions(
                self.url,
                self.actions,
                self.stop_event,
                on_saving=lambda: self.status_changed.emit("Preparing preview..."),
            )
            if result:
                preview_gif, raw_frames, total_duration = result
                self.finished_rerun.emit(preview_gif, raw_frames, total_duration)
            else:
                self.finished_rerun.emit("", [], 0.0)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.stop_event.set()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PRIMR")

        self.worker: RecordWorker | ReRunWorker | None = None
        self.recorded_actions: list[dict] = []
        self.last_temp_dir: str | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # --- Page 0: Main Setup UI ---
        setup_page = QWidget()
        setup_layout = QHBoxLayout(setup_page)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        setup_layout.addWidget(splitter)

        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        url_section = QWidget()
        url_sec_layout = QHBoxLayout(url_section)
        url_label = QLabel("URL")
        self.url_text_field = QLineEdit("")
        self.url_text_field.setMinimumWidth(400)
        url_sec_layout.addWidget(url_label)
        url_sec_layout.addWidget(self.url_text_field)
        left_layout.addWidget(url_section)

        group_box = QGroupBox("Settings")
        box_layout = QVBoxLayout()
        self.scroll_to_click_cb = QCheckBox("Scroll to Click")
        self.scroll_to_click_cb.setChecked(True)
        box_layout.addWidget(self.scroll_to_click_cb)
        group_box.setLayout(box_layout)
        left_layout.addWidget(group_box)

        rec_btn = QPushButton("Start Record Actions")
        rec_btn.clicked.connect(self.on_click_record)
        left_layout.addWidget(rec_btn)

        self.action_list = ActionListWidget()
        left_layout.addWidget(self.action_list)

        self.rerun_btn = QPushButton("Re-run Actions")
        self.rerun_btn.clicked.connect(self.on_click_rerun)
        left_layout.addWidget(self.rerun_btn)

        # Right Panel
        self.playback = PlaybackWidget()

        splitter.addWidget(left_panel)
        splitter.addWidget(self.playback)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # --- Page 1: Stop UI ---
        recording_page = QWidget()
        rec_layout = QVBoxLayout(recording_page)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.clicked.connect(self.on_click_stop)
        rec_layout.addWidget(self.stop_btn)

        self.stack.addWidget(setup_page)      # Index 0
        self.stack.addWidget(recording_page)  # Index 1

    def on_click_record(self):
        url = self.url_text_field.text().strip()
        if not url or (self.worker and self.worker.isRunning()):
            return

        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("Stop Record")
        self.stop_btn.setMinimumHeight(150)
        self.stack.setCurrentIndex(1)

        self.worker = RecordWorker(url)
        self.worker.finished_recording.connect(self.on_recording_finished)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.start()

    def on_click_rerun(self):
        url = self.url_text_field.text().strip()
        updated_actions = self.action_list.get_actions()
        if not url or not updated_actions or (self.worker and self.worker.isRunning()):
            return

        self._cleanup_temp_dir()
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("Stop Re-run")
        self.stack.setCurrentIndex(1)
        self.showMinimized()  # Let Chrome sit unobstructed on screen

        self.worker = ReRunWorker(url, updated_actions)
        self.worker.status_changed.connect(self.on_rerun_status)
        self.worker.finished_rerun.connect(self.on_rerun_finished)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.start()

    def on_click_stop(self):
        if self.worker and self.worker.isRunning():
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("Stopping...")
            self.worker.stop()

    def on_recording_finished(self, actions: list):
        self.recorded_actions = actions
        self.action_list.set_actions(actions)
        self.stack.setCurrentIndex(0)

    def on_rerun_status(self, text: str):
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText(text)

    def on_rerun_finished(self, preview_gif: str, raw_frames: list, total_duration: float):
        if preview_gif:
            self.last_temp_dir = os.path.dirname(preview_gif)
            self.playback.load_recording(preview_gif, raw_frames, total_duration)
        self.stack.setCurrentIndex(0)

    def on_worker_error(self, error_msg: str):
        print("Worker error:", error_msg)
        self.stack.setCurrentIndex(0)
        self.showNormal()
        self.activateWindow()

    def _cleanup_temp_dir(self):
        if self.playback.movie:
            self.playback.movie.stop()
            self.playback.display.clear()
            self.playback.movie = None
        if self.last_temp_dir and os.path.exists(self.last_temp_dir):
            shutil.rmtree(self.last_temp_dir, ignore_errors=True)
            self.last_temp_dir = None

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        self._cleanup_temp_dir()
        super().closeEvent(event)
        