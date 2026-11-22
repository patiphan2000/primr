import os
import shutil

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QMovie
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PlaybackWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.movie: QMovie | None = None
        self.natural_size = QSize()
        self.gif_path = ""
        self.video_path = ""

        layout = QVBoxLayout(self)
        self.display = QLabel("No recording yet")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setMinimumSize(480, 320)
        self.display.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.display, stretch=1)

        controls = QHBoxLayout()
        self.toggle_btn = QPushButton("Pause")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_play)

        self.save_btn = QPushButton("Save MP4 & GIF")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.on_click_save)

        controls.addWidget(self.toggle_btn)
        controls.addWidget(self.save_btn)
        layout.addLayout(controls)

    def load_recording(self, preview_gif_path: str, gif_path: str, video_path: str):
        if self.movie:
            self.movie.stop()

        self.gif_path = gif_path
        self.video_path = video_path
        self.natural_size = QImageReader(gif_path).size()
        self.movie = QMovie(gif_path)
        self._update_scaled_size()
        self.display.setMovie(self.movie)
        self.movie.start()

        self.toggle_btn.setEnabled(True)
        self.toggle_btn.setText("Pause")
        self.save_btn.setEnabled(True)

    def on_click_save(self):
        if not self.gif_path or not self.video_path:
            return

        chosen_path, _ = QFileDialog.getSaveFileName(
            self, "Save Recording (MP4 & GIF)", "recording", "All Files (*)"
        )
        if not chosen_path:
            return

        base_path, _ = os.path.splitext(chosen_path)
        dst_mp4 = f"{base_path}.mp4"
        dst_gif = f"{base_path}.gif"

        if os.path.exists(self.video_path):
            shutil.copy2(self.video_path, dst_mp4)
        if os.path.exists(self.gif_path):
            shutil.copy2(self.gif_path, dst_gif)

        QMessageBox.information(self, "Saved", f"Saved:\n{dst_mp4}\n{dst_gif}")

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