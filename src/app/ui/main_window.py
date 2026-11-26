import os
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .action_list_widget import ActionListWidget
from .constants import ASPECT_RATIO_RESOLUTION
from .playback_widget import PlaybackWidget
from .worker import RecordWorker, ReRunWorker

     
class RadioSettingGroup(QWidget):
    valueChanged = Signal(str)

    def __init__(self, options, default: str, validator=None, parent=None):
        super().__init__(parent)
        self._validator = validator  # Optional function returning True/False
        self._current_btn = None

        layout = QHBoxLayout(self)
        self._group = QButtonGroup(self)

        for option in options:
            btn = QRadioButton(option)
            if option == default:
                btn.setChecked(True)
                self._current_btn = btn
            self._group.addButton(btn)
            layout.addWidget(btn)

        self._group.buttonClicked.connect(self._on_button_clicked)

    @property
    def value(self) -> str:
        return self._current_btn.text() if self._current_btn else ""

    def _on_button_clicked(self, clicked_btn: QRadioButton):
        # Ignore clicks on the already-selected button
        if clicked_btn is self._current_btn:
            return

        # Ask validator if the change is allowed; revert if canceled
        if self._validator and not self._validator():
            if self._current_btn:
                self._current_btn.setChecked(True)  # Automatically unchecks clicked_btn
            return

        self._current_btn = clicked_btn
        self.valueChanged.emit(self.value)

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

        # ===== URL =====
        url_section = QWidget()
        url_sec_layout = QHBoxLayout(url_section)
        url_label = QLabel("URL")
        self.url_text_field = QLineEdit("")
        self.url_text_field.setMinimumWidth(400)
        url_sec_layout.addWidget(url_label)
        url_sec_layout.addWidget(self.url_text_field)
        left_layout.addWidget(url_section)

        # ===== Settings =====
        box_layout = QVBoxLayout()
        group_box = QGroupBox("Settings")
        
        # === Window Setting ===
        # === Aspect Ratio Setting ===
        self.aspect_ratio_setting = RadioSettingGroup(
            options=ASPECT_RATIO_RESOLUTION,
            default='4:3',
            validator=lambda: self.confirm_clear_actions('Aspect Ratio'),
        )
        # Optional: react when it actually changes
        # self.aspect_ratio_setting.valueChanged.connect(self.on_aspect_ratio_changed)
        left_layout.addWidget(self.aspect_ratio_setting)

        # === Orientation Setting ===
        self.orientation_setting = RadioSettingGroup(
            options=['Landscape', 'Portrait'],
            default='Portrait',
            validator=lambda: self.confirm_clear_actions('Orientation'),
        )
        left_layout.addWidget(self.orientation_setting)
        
        # === Record Setting ===
        self.scroll_to_click_cb = QCheckBox("Scroll to Click")
        self.scroll_to_click_cb.setChecked(True)
        box_layout.addWidget(self.scroll_to_click_cb)
        left_layout.addWidget(group_box)
        
        group_box.setLayout(box_layout)

        # ===== Start Record =====
        rec_btn = QPushButton("Start Record Actions")
        rec_btn.clicked.connect(self.on_click_record)
        left_layout.addWidget(rec_btn)

        # ===== Action List =====
        self.action_list = ActionListWidget()
        left_layout.addWidget(self.action_list)

        self.rerun_btn = QPushButton("Re-run Actions")
        self.rerun_btn.clicked.connect(self.on_click_rerun)
        left_layout.addWidget(self.rerun_btn)

        # ===== Right Panel =====
        self.playback = PlaybackWidget()

        splitter.addWidget(left_panel)
        splitter.addWidget(self.playback)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # ===== Page 1: Stop UI =====
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

        self.worker = RecordWorker(
            url,
            aspect_ratio=self.aspect_ratio_setting.value,
            orientation=self.orientation_setting.value,
        )
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

        self.worker = ReRunWorker(
            url,
            updated_actions,
            aspect_ratio=self.aspect_ratio_setting.value,
            orientation=self.orientation_setting.value,
        )
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
        
    def confirm_clear_actions(self, setting_name: str) -> bool:
        if not self.recorded_actions:
            return True

        reply = QMessageBox.question(
            self,
            f"Change {setting_name}?",
            f"Changing {setting_name} will clear your recorded actions. Are you sure?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        confirm_clear = reply == QMessageBox.StandardButton.Ok
        if confirm_clear:
            self.recorded_actions = []
            self.action_list.set_actions(self.recorded_actions)
        return confirm_clear

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
        