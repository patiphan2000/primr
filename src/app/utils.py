import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS) # type: ignore
    else:
        # Points from src/my_app/utils.py -> project root
        base_path = Path(__file__).resolve().parents[2]
    return base_path / "resources" / relative_path