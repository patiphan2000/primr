from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ActionItemWidget(QFrame):
    def __init__(self, action: dict, parent=None):
        super().__init__(parent)
        self.action = action
        self._drag_start_pos = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.handle = QLabel("⋮⋮")
        self.handle.setFixedWidth(20)
        self.handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.handle.setCursor(Qt.CursorShape.OpenHandCursor)
        layout.addWidget(self.handle)

        layout.addWidget(self._build_content(action), stretch=1)

    def _build_content(self, action: dict) -> QWidget:
        
        action_wdg = QWidget()
        wdg_layout = QVBoxLayout(action_wdg)
        
        # Get action type
        action_type = action.get("action", "unknown")
        
        # Extend here per action_type (e.g., "click", "scroll")
        match action_type:
            case "click":
                wdg_layout.addWidget(QLabel(str(action_type).capitalize()))
            case "scroll":
                wdg_layout.addWidget(QLabel(str(action_type).capitalize()))
                
                # Y target
                _x_target, _y_target = action['target']
                y_target_section = QWidget()
                y_target_section_layout = QHBoxLayout(y_target_section)
                y_label = QLabel("Y Target")
                y_target_edit = QLineEdit(str(_y_target))
                y_target_edit.setMaximumWidth(150)
                y_target_section_layout.addWidget(y_label)
                y_target_section_layout.addWidget(y_target_edit)
                wdg_layout.addWidget(y_target_section)
            case _:
                wdg_layout.addWidget(QLabel(str(action_type).capitalize()))
        
        return action_wdg

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.handle.geometry().contains(event.pos()):
            self._drag_start_pos = event.pos()
        else:
            self._drag_start_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag_start_pos:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.action.get("type", ""))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start_pos = None


class ActionListWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._container.setAcceptDrops(True)
        self._layout = QVBoxLayout(self._container)
        self._layout.addStretch()
        self.setWidget(self._container)

        self._container.dragEnterEvent = self._drag_enter_event
        self._container.dragMoveEvent = self._drag_move_event
        self._container.dropEvent = self._drop_event

    def set_actions(self, actions: list[dict]):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget(): # type: ignore
                item.widget().deleteLater() # type: ignore

        for action in actions:
            self._layout.insertWidget(self._layout.count() - 1, ActionItemWidget(action, self._container))

    def get_actions(self) -> list[dict]:
        return [
            self._layout.itemAt(i).widget().action # type: ignore
            for i in range(self._layout.count() - 1)
        ]

    def _drag_enter_event(self, event):
        if isinstance(event.source(), ActionItemWidget):
            event.acceptProposedAction()

    def _drag_move_event(self, event):
        if isinstance(event.source(), ActionItemWidget):
            event.acceptProposedAction()

    def _drop_event(self, event):
        source = event.source()
        if not isinstance(source, ActionItemWidget):
            return

        drop_y = event.position().y()
        item_count = self._layout.count() - 1
        target_index = item_count

        for i in range(item_count):
            w = self._layout.itemAt(i).widget() # type: ignore
            if drop_y < w.y() + w.height() / 2: # type: ignore
                target_index = i
                break

        current_index = self._layout.indexOf(source)
        self._layout.removeWidget(source)
        if current_index < target_index:
            target_index -= 1
        self._layout.insertWidget(target_index, source)
        event.acceptProposedAction()