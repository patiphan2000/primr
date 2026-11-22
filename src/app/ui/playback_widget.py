from PySide6.QtCore import Qt
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class PlaybackWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.movie = None

        layout = QVBoxLayout(self)
        self.display = QLabel("No recording yet")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setMinimumSize(480, 320)
        self.display.setScaledContents(False)
        layout.addWidget(self.display, stretch=1)

        controls = QHBoxLayout()
        self.toggle_btn = QPushButton("Pause")
        self.toggle_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.toggle_btn)
        layout.addLayout(controls)

    def load_gif(self, gif_path: str):
        if self.movie:
            self.movie.stop()
        self.movie = QMovie(gif_path)
        self.movie.setScaledSize(self.display.size())  # Scale to fit preview
        self.display.setMovie(self.movie)
        self.movie.start()
        self.toggle_btn.setText("Pause")

    def toggle_play(self):
        if not self.movie:
            return
        paused = self.movie.state() == QMovie.MovieState.Paused
        self.movie.setPaused(not paused)
        self.toggle_btn.setText("Pause" if paused else "Play")