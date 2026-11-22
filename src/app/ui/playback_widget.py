import os

from PySide6.QtCore import QSize, QStandardPaths, Qt
from PySide6.QtGui import QImageReader, QMovie
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.page_action import export_gif, export_video


class PlaybackWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.movie: QMovie | None = None
        self.natural_size = QSize()
        self.raw_frames: list[tuple[float, bytes]] = []
        self.total_duration: float = 0.0
        self.gif_path = ""
        self.video_path = ""

        layout = QVBoxLayout(self)
        self.display = QLabel("No recording yet")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setMinimumSize(480, 320)
        self.display.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.display, stretch=1)

        controls = QHBoxLayout()
        self.toggle_btn = QPushButton("Save MP4")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.on_click_save_video)

        self.save_btn = QPushButton("Save GIF")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.on_click_save_gif)

        controls.addWidget(self.toggle_btn)
        controls.addWidget(self.save_btn)
        layout.addLayout(controls)

    def load_recording(
        self,
        preview_gif_path: str,
        raw_frames: list[tuple[float, bytes]],
        total_duration: float,
    ):
        if self.movie:
            self.movie.stop()

        self.raw_frames = raw_frames
        self.total_duration = total_duration
        self.natural_size = QImageReader(preview_gif_path).size()
        self.movie = QMovie(preview_gif_path)
        self._update_scaled_size()
        self.display.setMovie(self.movie)
        self.movie.start()

        self.toggle_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
            
    def on_click_save_video(self):
        if not self.raw_frames:
            return
        default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        default_path = os.path.join(default_dir, "recording")
        chosen_path, _ = QFileDialog.getSaveFileName(
            self, "Save Recording MP4", default_path, "All Files (*)"
        )
        if not chosen_path:
            return

        base_path, _ = os.path.splitext(chosen_path)
        dst_mp4 = f"{base_path}.mp4"

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving...")
        QApplication.processEvents()
        try:
            export_video(
                self.raw_frames,
                self.total_duration,
                video_path=dst_mp4,
                video_fps=60
            )
            QMessageBox.information(self, "Saved", f"Saved:\n{dst_mp4}")
        finally:
            self.save_btn.setEnabled(True)
            self.save_btn.setText("Save MP4")
    
    def on_click_save_gif(self):
            if not self.raw_frames:
                return
            default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
            default_path = os.path.join(default_dir, "recording")
            chosen_path, _ = QFileDialog.getSaveFileName(
                self, "Save Recording GIF", default_path, "All Files (*)"
            )
            if not chosen_path:
                return
    
            base_path, _ = os.path.splitext(chosen_path)
            dst_gif = f"{base_path}.gif"
    
            self.save_btn.setEnabled(False)
            self.save_btn.setText("Saving...")
            QApplication.processEvents()
            try:
                export_gif(
                    self.raw_frames,
                    self.total_duration,
                    gif_path=dst_gif,
                    gif_fps=60
                )
                QMessageBox.information(self, "Saved", f"Saved:\n{dst_gif}")
            finally:
                self.save_btn.setEnabled(True)
                self.save_btn.setText("Save GIF")
            
    def _update_scaled_size(self):
        if not self.movie or not self.natural_size.isValid():
            return
        scaled = self.natural_size.scaled(
            self.display.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.movie.setScaledSize(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_size()

    def toggle_play(self):
        if not self.movie:
            return
        paused = self.movie.state() == QMovie.MovieState.Paused
        self.movie.setPaused(not paused)
        self.toggle_btn.setText("Pause" if paused else "Play")