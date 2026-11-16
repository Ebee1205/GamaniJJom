"""Resolve resources independently of the working directory."""
from pathlib import Path

from PySide6.QtGui import QIcon

RESOURCE_ROOT = Path(__file__).resolve().parents[2] / "resource"


def icon(name: str) -> QIcon:
    return QIcon(str(RESOURCE_ROOT / "icons" / f"{name}.svg"))


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet((RESOURCE_ROOT / "qss/theme.qss").read_text(encoding="utf-8"))
