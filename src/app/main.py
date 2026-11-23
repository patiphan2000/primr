import sys

from PySide6.QtWidgets import QApplication

from app.ui import MainWindow
from app.utils import resource_path


def load_stylesheet(app: QApplication, relative_path: str = "styles/main.qss"):
    qss_file = resource_path(relative_path)
    if qss_file.exists():
        print(qss_file)
        app.setStyleSheet(qss_file.read_text(encoding="utf-8"))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    load_stylesheet(app, "styles/main.qss")
    window = MainWindow()
    window.show()
    app.exec()