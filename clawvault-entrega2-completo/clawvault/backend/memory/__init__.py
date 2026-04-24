"""ClawVault - Sistema de memória hierárquica e multi-agente."""

from .manager import memory, MemoryEntry, MemoryManager
from .vault import (
    Vault,
    VaultNote,
    vault,
    extract_wikilinks,
    resolve_wikilink,
    ensure_vault_structure,
    VAULT_STRUCTURE,
)
from .multi_agent import (
    AgentRegistry,
    ProgressiveAgentMemory,
    SharedMemoryBus,
    LearningLoop,
    MemoryLevel,
    shared_bus,
    get_agent_memory,
    ensure_multi_agent_schema,
)

__all__ = [
    # Memória hierárquica básica
    "memory", "MemoryEntry", "MemoryManager",
    # Vault (segundo cérebro)
    "Vault", "VaultNote", "vault",
    "extract_wikilinks", "resolve_wikilink",
    "ensure_vault_structure", "VAULT_STRUCTURE",
    # Multi-agente
    "AgentRegistry", "ProgressiveAgentMemory",
    "SharedMemoryBus", "LearningLoop",
    "MemoryLevel", "shared_bus",
    "get_agent_memory", "ensure_multi_agent_schema",
]
