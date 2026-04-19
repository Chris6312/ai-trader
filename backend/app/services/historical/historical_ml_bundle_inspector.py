from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(slots=True)
class HistoricalMLBundleArtifactStatus:
    artifact_path: Path | None
    verified_artifact: bool
    source: str | None = None


class HistoricalMLBundleInspector:
    def load_manifest(self, manifest_path: Path) -> dict[str, object]:
        return cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))

    def resolve_model_artifact_status(
        self,
        *,
        manifest: dict[str, Any],
        manifest_path: Path,
        allow_missing: bool = True,
    ) -> HistoricalMLBundleArtifactStatus:
        training_reference_path = self._artifact_path_from_reference(manifest=manifest, reference_type="model_training")
        if training_reference_path is not None:
            return HistoricalMLBundleArtifactStatus(
                artifact_path=training_reference_path,
                verified_artifact=training_reference_path.exists(),
                source="model_training_reference",
            )

        training_summary_path = self._artifact_path_from_training_summary(manifest)
        if training_summary_path is not None:
            return HistoricalMLBundleArtifactStatus(
                artifact_path=training_summary_path,
                verified_artifact=training_summary_path.exists(),
                source="training_summary",
            )

        bundle_local_path = manifest_path.parent / "model_artifact.joblib"
        if bundle_local_path.exists() or allow_missing:
            return HistoricalMLBundleArtifactStatus(
                artifact_path=bundle_local_path if bundle_local_path.exists() or allow_missing else None,
                verified_artifact=bundle_local_path.exists(),
                source="bundle_local_default",
            )

        return HistoricalMLBundleArtifactStatus(artifact_path=None, verified_artifact=False, source=None)

    @staticmethod
    def artifact_reference_present(*, manifest: dict[str, Any], reference_type: str) -> bool:
        references = cast(list[dict[str, object]], manifest.get("references", []))
        return any(str(reference.get("reference_type") or "") == reference_type for reference in references)

    @staticmethod
    def _artifact_path_from_reference(*, manifest: dict[str, Any], reference_type: str) -> Path | None:
        references = cast(list[dict[str, object]], manifest.get("references", []))
        for reference in references:
            if str(reference.get("reference_type") or "") != reference_type:
                continue
            artifact_path = reference.get("artifact_path")
            if isinstance(artifact_path, str) and artifact_path:
                return Path(artifact_path)
        return None

    @staticmethod
    def _artifact_path_from_training_summary(manifest: dict[str, Any]) -> Path | None:
        training_summary = cast(dict[str, object], manifest.get("training_summary", {}))
        artifact_path = training_summary.get("artifact_path")
        if isinstance(artifact_path, str) and artifact_path:
            return Path(artifact_path)
        return None
