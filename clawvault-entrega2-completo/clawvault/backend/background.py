"""
ClawVault - Background Worker
==============================

CORREÇÃO vs P1 original: logging estruturado (print → journalctl).
"""

import threading
import time
from queue import Queue, Empty
from typing import Any, Callable, Optional

from backend.core.database import db


class BackgroundWorker:
    """Worker singleton que processa jobs em fila."""

    def __init__(self, poll_interval: float = 2.0):
        self.queue: Queue = Queue()
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.poll_interval = poll_interval
        self._stats = {
            "jobs_processed": 0,
            "jobs_failed":    0,
            "started_at":     None,
        }

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._stats["started_at"] = time.time()
        self.thread = threading.Thread(
            target=self._loop, daemon=True, name="clawvault-worker"
        )
        self.thread.start()
        print("[worker] Background worker iniciado (daemon thread)")

    def stop(self) -> None:
        self.running = False
        print("[worker] Background worker parando...")

    def _loop(self) -> None:
        while self.running:
            try:
                job = self.queue.get(timeout=self.poll_interval)
            except Empty:
                continue

            try:
                func, args, kwargs = job
                func(*args, **kwargs)
                self._stats["jobs_processed"] += 1
            except Exception as e:
                self._stats["jobs_failed"] += 1
                print(f"[worker] ERROR job failed: {e}")
            finally:
                self.queue.task_done()

    def enqueue(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        self.queue.put((func, args, kwargs))

    def enqueue_fact_extraction(self, conv_id: int) -> None:
        self.enqueue(_run_fact_extraction, conv_id)

    def enqueue_reindex_note(self, file_path: str) -> None:
        self.enqueue(_run_reindex_note, file_path)

    def stats(self) -> dict:
        uptime = (time.time() - self._stats["started_at"]) if self._stats["started_at"] else 0
        return {
            "running":         self.running,
            "queue_size":      self.queue.qsize(),
            "jobs_processed":  self._stats["jobs_processed"],
            "jobs_failed":     self._stats["jobs_failed"],
            "uptime_seconds":  int(uptime),
        }


def _run_fact_extraction(conv_id: int) -> None:
    try:
        from backend.fact_extractor import extractor
        result = extractor.extract_from_conversation(conv_id)
        print(f"[worker] Fact extraction conv={conv_id}: {result}")
    except Exception as e:
        print(f"[worker] ERROR fact extraction conv={conv_id}: {e}")


def _run_reindex_note(file_path: str) -> None:
    try:
        from pathlib import Path
        from backend.search import index_note
        chunks = index_note(Path(file_path))
        print(f"[worker] Reindexed {file_path}: {chunks} chunks")
    except Exception as e:
        print(f"[worker] ERROR reindex {file_path}: {e}")


def should_extract_facts(conv_id: int) -> bool:
    msgs = db.fetch_one(
        """
        SELECT COUNT(*) AS n,
               MAX(created_at) AS last_msg
        FROM messages WHERE conversation_id = ?
        """,
        (conv_id,),
    )

    if not msgs or (msgs["n"] or 0) < 4:
        return False

    existing = db.fetch_one(
        """
        SELECT id FROM facts
        WHERE source_conv = ?
          AND date(created_at) = date('now')
        LIMIT 1
        """,
        (conv_id,),
    )
    if existing:
        return False

    return True


# Instância global
worker = BackgroundWorker()
