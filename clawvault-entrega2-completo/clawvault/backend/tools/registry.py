"""
ClawVault — Tool Registry.

Central registry that holds all available tools, lists their schemas,
and dispatches execution by name.
"""

from __future__ import annotations
import logging
from typing import Any

from backend.tools.base import Tool

logger = logging.getLogger("clawvault.tools")


class ToolRegistry:
    """Central registry for all available function calling tools.

    Tools auto-register via Tool.__init_subclass__.
    Provides schema listing for LLM tool_choice and dispatch by name.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] Registered tool: {tool.name}")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            result = tool.execute(**arguments)
            logger.info(f"[ToolRegistry] Executed {name} with {list(arguments.keys())} → {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"[ToolRegistry] Error executing {name}: {e}")
            return f"Error executing {name}: {e}"


# Global singleton
registry = ToolRegistry()
