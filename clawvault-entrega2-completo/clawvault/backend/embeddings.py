"""
ClawVault - Embeddings Local (sem custo)
=========================================

CORREÇÃO vs P2 original: numpy batch cosine similarity onde disponível.
"""

import hashlib
import json
import math
import os
import struct
import urllib.request
import urllib.error
from typing import Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ==========================================================================
# CONFIGURAÇÃO
# ==========================================================================

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIM = 768
TIMEOUT_SECONDS = 30
USE_FALLBACK_IF_OLLAMA_DOWN = True

# Cache em memória
_memory_cache: dict[str, list[float]] = {}
_MEMORY_CACHE_MAX = 1000


def _embed_via_ollama(text: str) -> Optional[list[float]]:
    try:
        url = f"{OLLAMA_HOST.rstrip('/')}/api/embeddings"
        body = json.dumps({"model": OLLAMA_MODEL, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            vec = data.get("embedding")
            if isinstance(vec, list) and len(vec) > 0:
                return vec
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    return None


def _embed_fallback(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    seed = h
    while len(vec) < dim:
        seed = hashlib.sha256(seed).digest()
        for i in range(0, 32, 4):
            if len(vec) >= dim:
                break
            n = struct.unpack("I", seed[i:i + 4])[0]
            vec.append((n / 2**32) * 2 - 1)
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


def embed(text: str, use_cache: bool = True) -> list[float]:
    text = (text or "").strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    if use_cache and text in _memory_cache:
        return _memory_cache[text]

    vec = _embed_via_ollama(text)

    if vec is None:
        if USE_FALLBACK_IF_OLLAMA_DOWN:
            vec = _embed_fallback(text)
        else:
            raise RuntimeError(
                f"Não foi possível gerar embedding via Ollama em {OLLAMA_HOST}."
            )

    if use_cache:
        if len(_memory_cache) >= _MEMORY_CACHE_MAX:
            _memory_cache.pop(next(iter(_memory_cache)))
        _memory_cache[text] = vec

    return vec


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batch embed — mesma velocidade (Ollama não tem batch API) mas cache inteligente."""
    return [embed(t) for t in texts]


def similarity(vec1: list[float], vec2: list[float]) -> float:
    """Cosine similarity — usa numpy se disponível."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    if HAS_NUMPY:
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(dot / norm) if norm > 0 else 0.0

    # Fallback sem numpy
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def batch_similarity(query_vec: list[float], candidate_vecs: list[list[float]]) -> list[float]:
    """
    CORREÇÃO: batch cosine similarity com numpy.
    Retorna lista de scores na mesma ordem dos candidatos.
    """
    if not candidate_vecs:
        return []

    if HAS_NUMPY:
        q = np.array(query_vec, dtype=np.float32)
        C = np.array(candidate_vecs, dtype=np.float32)
        # Normalizar
        q_norm = q / (np.linalg.norm(q) + 1e-10)
        C_norms = np.linalg.norm(C, axis=1, keepdims=True) + 1e-10
        C_normalized = C / C_norms
        scores = np.dot(C_normalized, q_norm)
        return scores.tolist()

    # Fallback sem numpy
    return [similarity(query_vec, v) for v in candidate_vecs]


def serialize_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def health_check() -> dict:
    try:
        url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            has_model = any(OLLAMA_MODEL in m for m in models)
            return {
                "ok": True,
                "ollama_host": OLLAMA_HOST,
                "models_available": models,
                "embedding_model": OLLAMA_MODEL,
                "model_installed": has_model,
                "fallback_active": False,
                "numpy_available": HAS_NUMPY,
            }
    except Exception as e:
        return {
            "ok": False,
            "ollama_host": OLLAMA_HOST,
            "error": str(e),
            "fallback_active": USE_FALLBACK_IF_OLLAMA_DOWN,
            "numpy_available": HAS_NUMPY,
            "warning": (
                "Ollama não acessível — usando fallback determinístico. "
                "Para qualidade real, instale: ollama pull " + OLLAMA_MODEL
            ),
        }
