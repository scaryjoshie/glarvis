"""ToolHandle — single interface for tool-to-system communication.

Created by orchestrator at registration time. Tools access system capabilities
through self.handle rather than reaching into orchestrator internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glarvis.tool import TaskResult


class ToolHandle:
    def __init__(self, orchestrator: Any, tool_name: str):
        self._orch = orchestrator
        self._name = tool_name

    @property
    def system(self):
        """Live SystemMonitor reference."""
        return self._orch.system_monitor

    async def post_to_board(self, content: str, author: str | None = None) -> int:
        return await self._orch.broadcast_board_post(author or self._name, content)

    async def open_popup(self, popup_type: str, data: dict) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_open", "popup_type": popup_type,
            "tool_name": self._name, "data": data,
        })

    async def close_popup(self) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": self._name,
        })

    async def close_named_popup(self, name: str) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": name,
        })

    async def execute_tool(self, tool_name: str, **kwargs) -> TaskResult:
        return await self._orch.execute_tool(tool_name, kwargs)
