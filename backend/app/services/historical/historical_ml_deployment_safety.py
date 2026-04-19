from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.historical.historical_ml_deployment_safety_schemas import (
    HistoricalMLDeploymentActionSummary,
    HistoricalMLDeploymentAuditEvent,
    HistoricalMLDeploymentStateSummary,
)


class HistoricalMLDeploymentSafetyService:
    def __init__(
        self,
        session: Session,
        *,
        bundle_dir: str | Path | None = None,
    ) -> None:
        self._session = session
        default_root = Path(gettempdir()) / "ai_trader_ml_artifacts" / "_persisted_model_bundles"
        self._bundle_dir = Path(bundle_dir) if bundle_dir is not None else default_root
        self._bundle_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self._bundle_dir / "deployment_state.json"

    def get_state(self) -> HistoricalMLDeploymentStateSummary:
        payload = self._read_state_payload()
        return self._deserialize_state(payload)

    def approve_candidate(
        self,
        *,
        bundle_version: str,
        actor: str,
        notes: str | None = None,
    ) -> HistoricalMLDeploymentActionSummary:
        self._ensure_bundle_exists(bundle_version)
        state = self.get_state()
        approved = set(state.approved_candidate_versions)
        approved.add(bundle_version)
        state.approved_candidate_versions = sorted(approved)
        event = self._build_event(
            action="candidate_approved",
            bundle_version=bundle_version,
            actor=actor,
            notes=notes,
        )
        state.change_history.append(event)
        self._persist_state(state)
        return HistoricalMLDeploymentActionSummary(state=state, event=event)

    def promote_bundle(
        self,
        *,
        bundle_version: str,
        actor: str,
        notes: str | None = None,
    ) -> HistoricalMLDeploymentActionSummary:
        self._ensure_bundle_exists(bundle_version)
        state = self.get_state()
        if state.frozen_bundle_version is not None and state.frozen_bundle_version != bundle_version:
            raise ValueError(f"deployment is frozen on bundle {state.frozen_bundle_version}")
        if bundle_version not in state.approved_candidate_versions:
            raise ValueError(f"bundle {bundle_version} is not approved for promotion")

        previous_active = state.active_bundle_version
        state.active_bundle_version = bundle_version
        event = self._build_event(
            action="bundle_promoted",
            bundle_version=bundle_version,
            actor=actor,
            notes=notes,
            metadata={"previous_active_bundle_version": previous_active},
        )
        state.change_history.append(event)
        self._persist_state(state)
        return HistoricalMLDeploymentActionSummary(state=state, event=event)

    def rollback_bundle(
        self,
        *,
        actor: str,
        notes: str | None = None,
    ) -> HistoricalMLDeploymentActionSummary:
        state = self.get_state()
        if state.frozen_bundle_version is not None:
            raise ValueError(f"deployment is frozen on bundle {state.frozen_bundle_version}")
        if state.active_bundle_version is None:
            raise ValueError("no active bundle is available to roll back")

        prior_promotions = [
            event
            for event in state.change_history
            if event.action == "bundle_promoted" and event.bundle_version != state.active_bundle_version
        ]
        if not prior_promotions:
            raise ValueError("no previous promoted bundle is available for rollback")

        rollback_target = prior_promotions[-1].bundle_version
        current_active = state.active_bundle_version
        state.active_bundle_version = rollback_target
        event = self._build_event(
            action="bundle_rolled_back",
            bundle_version=rollback_target,
            actor=actor,
            notes=notes,
            metadata={"replaced_bundle_version": current_active},
        )
        state.change_history.append(event)
        self._persist_state(state)
        return HistoricalMLDeploymentActionSummary(state=state, event=event)

    def freeze_bundle(
        self,
        *,
        bundle_version: str,
        actor: str,
        reason: str | None = None,
    ) -> HistoricalMLDeploymentActionSummary:
        self._ensure_bundle_exists(bundle_version)
        state = self.get_state()
        state.frozen_bundle_version = bundle_version
        state.freeze_reason = reason
        event = self._build_event(
            action="bundle_frozen",
            bundle_version=bundle_version,
            actor=actor,
            notes=reason,
        )
        state.change_history.append(event)
        self._persist_state(state)
        return HistoricalMLDeploymentActionSummary(state=state, event=event)

    def unfreeze_bundle(
        self,
        *,
        actor: str,
        notes: str | None = None,
    ) -> HistoricalMLDeploymentActionSummary:
        state = self.get_state()
        current_bundle = state.frozen_bundle_version
        if current_bundle is None:
            raise ValueError("deployment is not currently frozen")
        state.frozen_bundle_version = None
        state.freeze_reason = None
        event = self._build_event(
            action="bundle_unfrozen",
            bundle_version=current_bundle,
            actor=actor,
            notes=notes,
        )
        state.change_history.append(event)
        self._persist_state(state)
        return HistoricalMLDeploymentActionSummary(state=state, event=event)

    def _ensure_bundle_exists(self, bundle_version: str) -> None:
        manifest_path = self._bundle_dir / bundle_version / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"unknown bundle_version: {bundle_version}")

    def _read_state_payload(self) -> dict[str, object]:
        if not self._state_path.exists():
            return {
                "active_bundle_version": None,
                "approved_candidate_versions": [],
                "frozen_bundle_version": None,
                "freeze_reason": None,
                "change_history": [],
            }
        return json.loads(self._state_path.read_text(encoding="utf-8"))

    def _deserialize_state(self, payload: dict[str, object]) -> HistoricalMLDeploymentStateSummary:
        history_payload = payload.get("change_history") or []
        history: list[HistoricalMLDeploymentAuditEvent] = []
        for item in history_payload:
            if not isinstance(item, dict):
                continue
            occurred_at = self._parse_datetime(item.get("occurred_at"))
            history.append(
                HistoricalMLDeploymentAuditEvent(
                    event_id=str(item.get("event_id") or ""),
                    action=str(item.get("action") or "candidate_approved"),
                    bundle_version=str(item.get("bundle_version") or ""),
                    actor=str(item.get("actor") or "system"),
                    notes=str(item.get("notes")) if item.get("notes") is not None else None,
                    occurred_at=occurred_at,
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        return HistoricalMLDeploymentStateSummary(
            active_bundle_version=self._optional_str(payload.get("active_bundle_version")),
            approved_candidate_versions=[str(item) for item in payload.get("approved_candidate_versions") or []],
            frozen_bundle_version=self._optional_str(payload.get("frozen_bundle_version")),
            freeze_reason=self._optional_str(payload.get("freeze_reason")),
            change_history=history,
        )

    def _persist_state(self, state: HistoricalMLDeploymentStateSummary) -> None:
        payload = asdict(state)
        self._state_path.write_text(
            json.dumps(payload, default=self._json_default, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _build_event(
        self,
        *,
        action: str,
        bundle_version: str,
        actor: str,
        notes: str | None,
        metadata: dict[str, object] | None = None,
    ) -> HistoricalMLDeploymentAuditEvent:
        return HistoricalMLDeploymentAuditEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            action=action,
            bundle_version=bundle_version,
            actor=actor,
            notes=notes,
            occurred_at=datetime.now(UTC),
            metadata=dict(metadata or {}),
        )

    def _parse_datetime(self, value: object) -> datetime:
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
            except ValueError:
                pass
        return datetime.now(UTC)

    def _optional_str(self, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _json_default(self, value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"unsupported json value: {type(value)!r}")
