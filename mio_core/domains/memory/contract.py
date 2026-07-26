"""MIO Core · Memory Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MemEvents:
    STORED = "memory.stored"
    RECALLED = "memory.recalled"
    CONSOLIDATED = "memory.consolidated"
    FORGOTTEN = "memory.forgotten"
    WORKING_EVICTED = "memory.working_evicted"


OPERATIONS = ("remember", "note_working", "recall", "working_set", "consolidate", "forget", "stats")


def memory_contract() -> dict[str, Any]:
    return {
        "domain": "memory",
        "version": CONTRACT_VERSION,
        "description": "WM/STM/LTM/episodic/semantic/procedural bellek + yaşam-döngüsü (konsolidasyon/çürüme/buda).",
        "operations": list(OPERATIONS),
        "events": [MemEvents.STORED, MemEvents.RECALLED, MemEvents.CONSOLIDATED, MemEvents.FORGOTTEN,
                   MemEvents.WORKING_EVICTED],
        "layers": ["working", "short_term", "long_term", "episodic", "semantic", "procedural"],
        "invariants": ["WM sınırlı (7±2)", "konsolidasyon deterministik", "durable katmanlar budanmaz"],
    }
