"""Resolve resources independently of the working directory."""
from pathlib import Path
from functools import lru_cache
import re

from PySide6.QtGui import QColor, QIcon

RESOURCE_ROOT = Path(__file__).resolve().parents[2] / "resource"
APP_ICON_PATH = RESOURCE_ROOT / "app.ico"
_TOKEN_BLOCK = re.compile(r":root\s*\{([^{}]*)\}")
_TOKEN_DECLARATION = re.compile(r"--([a-z][a-z0-9-]*)\s*:\s*([^;{}]+);", re.ASCII)
_TOKEN_REFERENCE = re.compile(r"var\(\s*--([a-z][a-z0-9-]*)\s*\)", re.ASCII)


def icon(name: str) -> QIcon:
    return QIcon(str(RESOURCE_ROOT / "icons" / f"icon_{name}.svg"))


def app_icon() -> QIcon:
    return QIcon(str(APP_ICON_PATH))


def apply_theme(app) -> None:
    stylesheet = load_theme()
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet)


def load_theme(path: Path | None = None) -> str:
    """Resolve the theme's literal :root tokens before passing the QSS to Qt.

    Tokens use --name: value; and var(--name). Token values must be literals;
    nested variables and CSS fallback expressions are intentionally unsupported.
    """
    if path is None:
        _default_theme.cache_clear()
        return _default_theme()[0]
    return _parse_theme(path.resolve())[0]


@lru_cache(maxsize=1)
def _default_theme() -> tuple[str, dict[str, str]]:
    return _parse_theme((RESOURCE_ROOT / "qss" / "theme.qss").resolve())


def theme_token(name: str) -> str:
    tokens = _default_theme()[1]
    if name not in tokens:
        raise ValueError(f"Unknown theme token: --{name}")
    return tokens[name]


def theme_color(name: str) -> QColor:
    value = theme_token(name)
    rgba = re.fullmatch(
        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
        value,
    )
    if rgba:
        components = [int(component) for component in rgba.groups()]
        if any(component > 255 for component in components):
            raise ValueError(f"Invalid color for theme token --{name}: {value}")
        color = QColor(components[0], components[1], components[2], components[3])
    else:
        color = QColor(value)
    if not color.isValid():
        raise ValueError(f"Invalid color for theme token --{name}: {value}")
    return color


def _parse_theme(theme_path: Path) -> tuple[str, dict[str, str]]:
    source = theme_path.read_text(encoding="utf-8")
    # Comments are documentation, not declarations or Qt selectors.
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    blocks = list(_TOKEN_BLOCK.finditer(source))
    if len(blocks) != 1:
        raise ValueError("Theme must contain exactly one :root token block")
    body = blocks[0].group(1)
    tokens = {}
    for match in _TOKEN_DECLARATION.finditer(body):
        name, value = match.group(1), match.group(2).strip()
        if name in tokens:
            raise ValueError(f"Duplicate theme token: --{name}")
        if "var(" in value:
            raise ValueError(f"Theme token must have a literal value: --{name}")
        if re.search(r"--[a-z][a-z0-9-]*\s*:", value):
            raise ValueError(f"Missing semicolon after theme token: --{name}")
        tokens[name] = value
    if _TOKEN_DECLARATION.sub("", body).strip():
        raise ValueError("Invalid theme token declaration")

    def replace(match):
        name = match.group(1)
        if name not in tokens:
            raise ValueError(f"Unknown theme token: --{name}")
        return tokens[name]

    stylesheet = _TOKEN_REFERENCE.sub(replace, _TOKEN_BLOCK.sub("", source))
    if "var(" in stylesheet or ":root" in stylesheet:
        raise ValueError("Unresolved or unsupported theme token syntax")
    # Qt otherwise resolves relative image URLs against the process directory.
    stylesheet = re.sub(
        r'url\("(\.{1,2}/[^"\n]+)"\)',
        lambda match: f'url("{(theme_path.parent / match.group(1)).resolve().as_posix()}")',
        stylesheet,
    )
    return stylesheet, tokens
