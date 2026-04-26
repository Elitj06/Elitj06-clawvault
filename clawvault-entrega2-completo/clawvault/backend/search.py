"""
ClawVault - Busca Híbrida (BM25 + Embeddings)
==============================================

CORREÇÕES vs P2 original:
  - semantic_search() usa numpy batch cosine similarity
  - cache_lookup() usa numpy batch
  - Fallback para loop individual se numpy indisponível
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import VAULT_DIR
from backend.core.database import db
from backend.embeddings import (
    embed, embed_batch, similarity, batch_similarity,
    serialize_vector, deserialize_vector, HAS_NUMPY,
)
from backend.memory.vault import vault


WEIGHT_KEYWORD = 0.4
WEIGHT_SEMANTIC = 0.6
CHUNK_CHARS = 800


# ==========================================================================
# INDEXAÇÃO
# ==========================================================================

def index_note(file_path: Path) -> int:
    if not file_path.exists():
        return 0
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return 0
    if not content.strip():
        return 0

    rel_path = str(file_path.relative_to(VAULT_DIR))

    db.execute(
        "DELETE FROM embeddings WHERE source_type = 'note' AND file_path = ?",
        (rel_path,),
    )

    chunks = _chunk_text(content, CHUNK_CHARS)

    count = 0
    for chunk_text in chunks:
        if not chunk_text.strip():
            continue
        try:
            vec = embed(chunk_text)
            db.execute(
                """
                INSERT INTO embeddings
                  (source_type, source_id, file_path, chunk_text, embedding_blob, model_used)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("note", None, rel_path, chunk_text, serialize_vector(vec),
                 "nomic-embed-text"),
            )
            count += 1
        except Exception:
            continue
    return count


def reindex_all() -> dict:
    total_files = 0
    total_chunks = 0
    errors = 0

    for md_file in VAULT_DIR.rglob("*.md"):
        try:
            chunks = index_note(md_file)
            total_files += 1
            total_chunks += chunks
        except Exception:
            errors += 1

    return {
        "files_indexed": total_files,
        "chunks_created": total_chunks,
        "errors": errors,
        "completed_at": datetime.now().isoformat(),
    }


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = []
    current_size = 0
    for line in text.split("\n"):
        line_len = len(line) + 1
        if current_size + line_len > max_chars and current:
            chunks.append("\n".join(current))
            current = [line]
            current_size = line_len
        else:
            current.append(line)
            current_size += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


# ==========================================================================
# BUSCA SEMÂNTICA — COM NUMPY BATCH
# ==========================================================================

def semantic_search(
    query: str,
    limit: int = 10,
    min_score: float = 0.3,
) -> list[dict]:
    if not query.strip():
        return []

    query_vec = embed(query)

    rows = db.fetch_all(
        """
        SELECT id, source_type, file_path, chunk_text, embedding_blob
        FROM embeddings
        WHERE source_type = 'note'
        """
    )

    if not rows:
        return []

    # CORREÇÃO: batch com numpy ao invés de loop individual
    candidate_vecs = []
    valid_rows = []
    for r in rows:
        try:
            vec = deserialize_vector(r["embedding_blob"])
            candidate_vecs.append(vec)
            valid_rows.append(r)
        except Exception:
            continue

    # Batch similarity
    scores = batch_similarity(query_vec, candidate_vecs)

    scored = []
    for i, (r, score) in enumerate(zip(valid_rows, scores)):
        if score >= min_score:
            scored.append({
                "path": r["file_path"],
                "snippet": (r["chunk_text"] or "")[:200],
                "score": score,
                "layer": _detect_layer(r["file_path"]),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    seen_paths = set()
    unique = []
    for s in scored:
        if s["path"] not in seen_paths:
            seen_paths.add(s["path"])
            unique.append(s)
            if len(unique) >= limit:
                break
    return unique


# ==========================================================================
# BUSCA HÍBRIDA
# ==========================================================================

def hybrid_search(
    query: str,
    limit: int = 10,
    layer: Optional[str] = None,
) -> list[dict]:
    K = 60

    keyword_results = vault.search(query, layer=layer, limit=20)
    keyword_rank = {r["path"]: i + 1 for i, r in enumerate(keyword_results)}

    semantic_results = semantic_search(query, limit=20)
    if layer:
        semantic_results = [r for r in semantic_results if r["layer"] == layer]
    semantic_rank = {r["path"]: i + 1 for i, r in enumerate(semantic_results)}

    all_paths = set(keyword_rank) | set(semantic_rank)
    fused = []
    for path in all_paths:
        score = 0.0
        if path in keyword_rank:
            score += WEIGHT_KEYWORD * (1.0 / (K + keyword_rank[path]))
        if path in semantic_rank:
            score += WEIGHT_SEMANTIC * (1.0 / (K + semantic_rank[path]))
        fused.append({"path": path, "fused_score": score})

    fused.sort(key=lambda x: x["fused_score"], reverse=True)

    snippet_map = {r["path"]: r.get("snippet", "") for r in keyword_results}
    for r in semantic_results:
        snippet_map.setdefault(r["path"], r.get("snippet", ""))

    final = []
    for f in fused[:limit]:
        final.append({
            "path": f["path"],
            "snippet": snippet_map.get(f["path"], ""),
            "score": round(f["fused_score"], 4),
            "in_keyword": f["path"] in keyword_rank,
            "in_semantic": f["path"] in semantic_rank,
            "layer": _detect_layer(f["path"]),
        })
    return final


# ==========================================================================
# CACHE SEMÂNTICO — COM NUMPY BATCH
# ==========================================================================

SEMANTIC_CACHE_THRESHOLD = 0.92
SEMANTIC_CACHE_TTL = 86400


def cache_lookup(query: str) -> Optional[dict]:
    if not query.strip():
        return None

    query_vec = embed(query)

    rows = db.fetch_all(
        """
        SELECT id, prompt_hash, model_id, response, hits, last_used_at
        FROM response_cache
        WHERE expires_at IS NULL OR expires_at > datetime('now')
        ORDER BY last_used_at DESC
        LIMIT 200
        """
    )

    if not rows:
        return None

    # CORREÇÃO: batch embed + batch similarity
    cached_texts = [r["prompt_hash"] or "" for r in rows]
    valid_indices = [i for i, t in enumerate(cached_texts) if t]

    if not valid_indices:
        return None

    valid_texts = [cached_texts[i] for i in valid_indices]
    cached_vecs = embed_batch(valid_texts)
    scores = batch_similarity(query_vec, cached_vecs)

    # Encontra o melhor match
    best_idx = 0
    best_score = scores[0] if scores else 0.0
    for i, score in enumerate(scores):
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score < SEMANTIC_CACHE_THRESHOLD:
        return None

    best_row_idx = valid_indices[best_idx]
    best = rows[best_row_idx]

    db.execute(
        """
        UPDATE response_cache
        SET hits = hits + 1, last_used_at = datetime('now')
        WHERE id = ?
        """,
        (best["id"],),
    )

    return {
        "response": best["response"],
        "model_id": best["model_id"],
        "original_query": best["prompt_hash"],
        "similarity": round(best_score, 4),
        "hits": best["hits"] + 1,
    }


def cache_store(query: str, response: str, model_id: str,
                tokens_saved: int = 0, ttl: int = SEMANTIC_CACHE_TTL) -> None:
    if not query.strip() or not response.strip():
        return

    import hashlib
    cache_key = hashlib.sha256(f"{query}|{model_id}".encode()).hexdigest()[:16]
    expires_at = (datetime.now().timestamp() + ttl) if ttl else None

    db.execute(
        """
        INSERT INTO response_cache
          (cache_key, prompt_hash, model_id, response, tokens_saved,
           hits, expires_at)
        VALUES (?, ?, ?, ?, ?, 0, datetime(?, 'unixepoch'))
        ON CONFLICT(cache_key) DO UPDATE SET
            response = excluded.response,
            last_used_at = CURRENT_TIMESTAMP,
            expires_at = excluded.expires_at
        """,
        (cache_key, query, model_id, response, tokens_saved, expires_at),
    )


def cache_clear(older_than_days: Optional[int] = None) -> int:
    if older_than_days:
        cursor = db.execute(
            "DELETE FROM response_cache WHERE last_used_at < datetime('now', ?)",
            (f"-{older_than_days} days",),
        )
    else:
        cursor = db.execute("DELETE FROM response_cache")
    return cursor.rowcount


# ==========================================================================
# HELPERS
# ==========================================================================

def _detect_layer(file_path: str) -> str:
    first = file_path.split("/")[0] if "/" in file_path else file_path
    if first.startswith("00_"):  return "raw"
    if first.startswith("10_"):  return "wiki"
    if first.startswith("20_"):  return "output"
    if first.startswith("30_"):  return "agents"
    if first.startswith("40_"):  return "skills"
    return "other"


def index_stats() -> dict:
    notes = db.fetch_one(
        """
        SELECT
            COUNT(DISTINCT file_path) AS files,
            COUNT(*) AS chunks
        FROM embeddings WHERE source_type = 'note'
        """
    )
    cache_stats = db.fetch_one(
        """
        SELECT
            COUNT(*) AS entries,
            COALESCE(SUM(hits), 0) AS total_hits,
            COALESCE(SUM(tokens_saved * hits), 0) AS tokens_saved
        FROM response_cache
        WHERE expires_at IS NULL OR expires_at > datetime('now')
        """
    )
    return {
        "vault_index": {
            "files_indexed":  notes["files"] or 0,
            "total_chunks":   notes["chunks"] or 0,
        },
        "response_cache": {
            "entries":        cache_stats["entries"] or 0,
            "total_hits":     cache_stats["total_hits"] or 0,
            "tokens_saved":   cache_stats["tokens_saved"] or 0,
        },
        "numpy_available": HAS_NUMPY,
    }
