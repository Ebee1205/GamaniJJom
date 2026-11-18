"""Renderer-independent toolbar tools, reusable by a dock/list renderer."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ToolbarTool:
    id: str
    icon: str
    label: str
    kind: Literal['action', 'toggle', 'submenu'] = 'action'
    children: tuple['ToolbarTool', ...] = ()


LOCK_TOOLS = (
    ToolbarTool('window_size', 'window_size', '창 크기 변경'),
)
WINDOW_TOOLS = (
    ToolbarTool('window_list', 'app_select', '창 목록'),
    ToolbarTool('disconnect', 'disconnect', '연결 해제'),
)
TOOLBAR_TOOLS = (
    ToolbarTool('app_select', 'app_select', '창 변경', 'action', WINDOW_TOOLS),
    ToolbarTool('lock', 'lock', '잠금', 'toggle', LOCK_TOOLS),
    ToolbarTool('more', 'more', '더보기'),
)
