from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HistoricalModelPersistenceConfig:
    bundle_name: str = "baseline_model_bundle"
    bundle_version_prefix: str = "12l_v1"
    include_optional_reports: bool = True
    copy_model_artifact: bool = True


@dataclass(slots=True)
class PersistedModelReference:
    reference_type: str
    reference_version: str
    artifact_path: str | None = None
    artifact_sha256: str | None = None


@dataclass(slots=True)
class HistoricalModelPersistenceSummary:
    bundle_version: str
    bundle_name: str
    strategy_name: str
    dataset_version: str
    model_version: str
    model_family: str
    label_key: str
    feature_keys: list[str] = field(default_factory=list)
    manifest_path: str = ""
    manifest_sha256: str | None = None
    model_artifact_path: str | None = None
    model_artifact_sha256: str | None = None
    reproducibility_fingerprint: str | None = None
    references: list[PersistedModelReference] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModelBundleVerificationSummary:
    bundle_version: str
    manifest_exists: bool
    artifact_exists: bool
    manifest_hash_matches: bool
    artifact_hash_matches: bool
    verified: bool
    notes: list[str] = field(default_factory=list)
