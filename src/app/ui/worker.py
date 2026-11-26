import threading

from PySide6.QtCore import QThread, Signal

from app.page_action import re_run_actions, record_page_actions


class RecordWorker(QThread):
    finished_recording = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self, 
        url: str,
        aspect_ratio: str,
        orientation: str,
    ):
        super().__init__()
        self.url = url
        self.stop_event = threading.Event()
        self.aspect_ratio = aspect_ratio
        self.orientation = orientation

    def run(self):
        try:
            actions = record_page_actions(
                self.url, 
                self.stop_event,
                self.aspect_ratio, # type: ignore
                self.orientation, # type: ignore
            )
            self.finished_recording.emit(actions)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.stop_event.set()


class ReRunWorker(QThread):
    status_changed = Signal(str)
    finished_rerun = Signal(str, object, float)
    error_occurred = Signal(str)

    def __init__(
        self, url: str, 
        actions: list[dict],
        aspect_ratio: str,
        orientation: str,
    ):
        super().__init__()
        self.url = url
        self.actions = actions
        self.stop_event = threading.Event()
        self.aspect_ratio = aspect_ratio
        self.orientation = orientation

    def run(self):
        try:
            result = re_run_actions(
                self.url,
                self.actions,
                self.stop_event,
                on_saving=lambda: self.status_changed.emit("Preparing preview..."),
                aspect_ratio=self.aspect_ratio, # type: ignore
                orientation=self.aspect_ratio, # type: ignore
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
