from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HistoricalMLBundleBuildSummary:
    bundle_version: str
    bundle_name: str
    dataset_version: str
    strategy_name: str
    model_version: str
    validation_version: str | None = None
    drift_report_version: str | None = None
    manifest_path: str = ""
    model_artifact_path: str | None = None
    verified_bundle: bool = False
    notes: list[str] = field(default_factory=list)
