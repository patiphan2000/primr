from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ActionItemWidget(QFrame):
    
    delete_requested = Signal(object)
    
    def __init__(self, action: dict, parent=None):
        super().__init__(parent)
        self.action = action
        self._drag_start_pos = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        layout.addWidget(self._build_content(action), stretch=1)

    def _get_action_label(self, action_label) -> QWidget:
        
        action_title = QWidget()
        title_layout = QHBoxLayout(action_title)
        title_layout.setStretch(0, 0)
        title_layout.setStretch(0, 0)
        
        # Set Icon
        icon = QIcon(f"resources/icons/{action_label}-icon.png")
        action_icon = QLabel()
        action_icon.setPixmap(icon.pixmap(24))
        title_layout.addWidget(action_icon)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Set font
        action_label = QLabel(str(action_label).capitalize())
        font = action_label.font()
        font.setPointSize(16)
        font.setBold(True)
        action_label.setFont(font)
        title_layout.addWidget(action_label)
        
        return action_title

    def _build_content(self, action: dict) -> QWidget:
        action_wdg = QWidget()
        action_wdg_layout = QHBoxLayout(action_wdg)
        
        left_wdg = QWidget()
        wdg_layout = QVBoxLayout(left_wdg)
        wdg_layout.addStretch()
        wdg_layout.setSpacing(0)
        wdg_layout.setContentsMargins(0, 0, 0, 0)

        action_type = action.get("action", "unknown")

        match action_type:
            case "wait":
                wdg_layout.addWidget(self._get_action_label(action_type))
                
                _wait_duration = action["duration"]
                duration_section = QWidget()
                duration_section_layout = QHBoxLayout(duration_section)
                duration_label = QLabel("Duration :")
                duration_unit_label = QLabel("seconds")
                duration_target_edit = QLineEdit(str(float(_wait_duration)))
                duration_target_edit.setMaximumWidth(150)
                duration_target_edit.setValidator(QDoubleValidator(0, 10, 2, duration_target_edit))
                duration_target_edit.textChanged.connect(self._on_wait_duration_changed)
                
                duration_section_layout.addWidget(duration_label)
                duration_section_layout.addWidget(duration_target_edit)
                duration_section_layout.addWidget(duration_unit_label)
                wdg_layout.addWidget(duration_section)

            case "scroll":
                wdg_layout.addWidget(self._get_action_label(action_type))

                _x_target, _y_target = action["target"]
                y_target_section = QWidget()
                y_target_section_layout = QHBoxLayout(y_target_section)
                
                # Label
                y_label = QLabel("Y Target :")
                
                # Y Target
                y_target_edit = QLineEdit(str(int(_y_target)))
                y_target_edit.setMaximumWidth(150)
                y_target_edit.setValidator(QIntValidator(0, 999999, y_target_edit))
                y_target_edit.textChanged.connect(self._on_y_target_changed)

                y_target_section_layout.addWidget(y_label)
                y_target_section_layout.addWidget(y_target_edit)
                wdg_layout.addWidget(y_target_section)

            case "click":
                wdg_layout.addWidget(self._get_action_label(action_type))

                # Target selector section
                _target = action.get("target", "")
                target_section = QWidget()
                target_section_layout = QHBoxLayout(target_section)
                target_label = QLabel("Target :")
                target_text = QLabel(str(_target))

                target_section_layout.addWidget(target_label)
                target_section_layout.addWidget(target_text)
                wdg_layout.addWidget(target_section)

                # Coordinates (X, Y) section
                _x_coord, _y_coord = action.get("coords", (0, 0))
                coords_section = QWidget()
                coords_section_layout = QHBoxLayout(coords_section)

                x_label = QLabel("X :")
                x_edit = QLineEdit(str(int(_x_coord)))
                x_edit.setMaximumWidth(70)
                x_edit.setValidator(QIntValidator(0, 999999, x_edit))
                x_edit.textChanged.connect(self._on_click_x_changed)

                y_label = QLabel("Y :")
                y_edit = QLineEdit(str(int(_y_coord)))
                y_edit.setMaximumWidth(70)
                y_edit.setValidator(QIntValidator(0, 999999, y_edit))
                y_edit.textChanged.connect(self._on_click_y_changed)

                coords_section_layout.addWidget(x_label)
                coords_section_layout.addWidget(x_edit)
                coords_section_layout.addWidget(y_label)
                coords_section_layout.addWidget(y_edit)
                wdg_layout.addWidget(coords_section)
                
                # Wait after click section
                _wait_after = action.get("wait_after_click", 0.0)
                wait_after_section = QWidget()
                wait_after_section_layout = QHBoxLayout(wait_after_section)
                wait_label = QLabel("Wait after click for :")
                wait_duration = QLineEdit(str(_wait_after))
                wait_duration.setMaximumWidth(60)
                wait_duration.setValidator(QDoubleValidator(0, 10, 2, wait_duration))
                wait_duration.textChanged.connect(self._on_click_wait_changed)
                wait_unit_label = QLabel("seconds")
                
                wait_after_section_layout.addWidget(wait_label)
                wait_after_section_layout.addWidget(wait_duration)
                wait_after_section_layout.addWidget(wait_unit_label)
                wdg_layout.addWidget(wait_after_section)
                
            case _:
                wdg_layout.addWidget(self._get_action_label(action_type))

        action_wdg_layout.addWidget(left_wdg)
        
        # Add delete button
        delete_btn = QPushButton()
        delete_btn.setObjectName("DeleteButton")
        delete_btn.setIcon(QIcon("resources/icons/delete-icon.png"))
        delete_btn.setIconSize(QSize(18, 18))  # Adjust icon size
        delete_btn.setToolTip("Delete action")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        action_wdg_layout.addWidget(delete_btn)
        
        return action_wdg
    
    def _on_wait_duration_changed(self, text: str):
        # if text.isdigit():
        self.action["duration"] = float(text)

    def _on_y_target_changed(self, text: str):
        if text.isdigit():
            x_target, _ = self.action["target"]
            self.action["target"] = (x_target, int(text))
    
    def _on_click_target_changed(self, text: str) -> None:
        self.action["target"] = text

    def _on_click_text_changed(self, text: str) -> None:
        self.action["text"] = text

    def _on_click_x_changed(self, text: str) -> None:
        if text:
            _, y = self.action.get("coords", (0, 0))
            self.action["coords"] = (int(text), y)

    def _on_click_y_changed(self, text: str) -> None:
        if text:
            x, _ = self.action.get("coords", (0, 0))
            self.action["coords"] = (x, int(text))
            
    def _on_click_wait_changed(self, text: str) -> None:
        if text:
            self.action["wait_after_click"] = float(text)


class ActionListWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._container.setAcceptDrops(True)
        self._layout = QVBoxLayout(self._container)
        self._layout.addStretch()
        self.setWidget(self._container)

    def set_actions(self, actions: list[dict]):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget(): # type: ignore
                item.widget().deleteLater() # type: ignore

        for action in actions:
            item_widget = ActionItemWidget(action, self._container)
            item_widget.delete_requested.connect(self._remove_action_item)
            self._layout.insertWidget(self._layout.count() - 1, item_widget)

    def get_actions(self) -> list[dict]:
        return [
            self._layout.itemAt(i).widget().action # type: ignore
            for i in range(self._layout.count() - 1)
        ]

    def _remove_action_item(self, item_widget: ActionItemWidget):
        self._layout.removeWidget(item_widget)
        item_widget.deleteLater()