from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver


@lru_cache(maxsize=1)
def get_checkpointer() -> MemorySaver:
    return MemorySaver()
