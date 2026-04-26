"""
ClawVault — Tool base class for Function Calling.

Every tool inherits from `Tool` and implements:
- name, description, parameters (JSON Schema)
- execute(**kwargs) -> str

Auto-registers in the global ToolRegistry on subclass instantiation.
"""

from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Base class for all ClawVault tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-register concrete tools (skip if name is empty = still abstract)
        if cls.name and cls not in (Tool,):
            from backend.tools.registry import registry
            registry.register(cls())

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return a string result."""
        ...

    def schema(self) -> dict[str, Any]:
        """Return OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
