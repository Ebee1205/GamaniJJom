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


MORE_TOOLS = (
    ToolbarTool('settings', 'settings', '설정'),
    ToolbarTool('app_select', 'app_select', '어플리케이션 지정'),
    ToolbarTool('window_size', 'window_size', '창 크기 설정'),
)
TOOLBAR_TOOLS = (
    ToolbarTool('pin', 'pin', '점착 / 떼기', 'toggle'),
    ToolbarTool('lock', 'lock', '대상 창 잠금', 'toggle'),
    ToolbarTool('more', 'more', '더보기', 'action'),
)
