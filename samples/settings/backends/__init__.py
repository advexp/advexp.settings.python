"""The minimal local backend this folder's samples run on."""

from backends.memory import (  # noqa: F401 - the re-export surface
    MemoryPlugin,
    MemorySerializer,
    MemorySetting,
    MemoryStorage,
    memory_setting,
)

__all__ = [
    "MemoryPlugin",
    "MemorySerializer",
    "MemorySetting",
    "MemoryStorage",
    "memory_setting",
]
