from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

DeploymentChangeAction = Literal[
    "candidate_approved",
    "bundle_promoted",
    "bundle_rolled_back",
    "bundle_frozen",
    "bundle_unfrozen",
]


@dataclass(slots=True)
class HistoricalMLDeploymentAuditEvent:
    event_id: str
    action: DeploymentChangeAction
    bundle_version: str
    actor: str
    notes: str | None
    occurred_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class HistoricalMLDeploymentStateSummary:
    active_bundle_version: str | None
    approved_candidate_versions: list[str] = field(default_factory=list)
    frozen_bundle_version: str | None = None
    freeze_reason: str | None = None
    change_history: list[HistoricalMLDeploymentAuditEvent] = field(default_factory=list)


@dataclass(slots=True)
class HistoricalMLDeploymentActionSummary:
    state: HistoricalMLDeploymentStateSummary
    event: HistoricalMLDeploymentAuditEvent
