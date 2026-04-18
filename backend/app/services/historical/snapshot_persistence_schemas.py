from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SnapshotPersistenceSummary:
    snapshot_kind: str
    rows_input: int
    rows_inserted: int
    rows_replaced: int
