"""ClawVault - Sistema de compressão humano→máquina."""

from .compressor import (
    HumanCompressor,
    ResponseHumanizer,
    CompressionResult,
    default_compressor,
    aggressive_compressor,
    humanizer,
)

__all__ = [
    "HumanCompressor",
    "ResponseHumanizer",
    "CompressionResult",
    "default_compressor",
    "aggressive_compressor",
    "humanizer",
]
