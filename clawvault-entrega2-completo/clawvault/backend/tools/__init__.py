"""ClawVault Tools — Function Calling infrastructure."""

from backend.tools.registry import registry

# Import builtins to trigger auto-registration via __init_subclass__
import backend.tools.builtins  # noqa: F401

__all__ = ["registry"]
