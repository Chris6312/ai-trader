from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import and_, delete, or_, tuple_
from sqlalchemy.orm import Session

from app.models.ai_research import (
    RegimeSnapshot,
    SentimentSnapshot,
    TechnicalSnapshot,
    UniverseSnapshot,
)
from app.services.historical.regime_detection_schemas import RegimeDetectionRecord
from app.services.historical.sentiment_scoring_schemas import SentimentScoreRecord
from app.services.historical.snapshot_persistence_schemas import SnapshotPersistenceSummary
from app.services.historical.technical_scoring_schemas import TechnicalScoreRecord
from app.services.historical.universe_composer_schemas import UniverseCandidateRecord


def _decimal_to_string(value: Decimal | object) -> str | object:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _normalize_json(payload: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            normalized[key] = _normalize_json(value)
        elif isinstance(value, list):
            normalized[key] = [
                _normalize_json(item) if isinstance(item, dict) else _decimal_to_string(item)
                for item in value
            ]
        else:
            normalized[key] = _decimal_to_string(value)
    return normalized


class AISnapshotPersistenceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def persist_technical_scores(
        self,
        records: Iterable[TechnicalScoreRecord],
    ) -> SnapshotPersistenceSummary:
        items = list(records)
        replaced = self._replace_existing(
            TechnicalSnapshot,
            [
                (item.symbol, item.asset_class, item.timeframe, item.candle_time, item.source_label)
                for item in items
            ],
        )
        for item in items:
            self._session.add(
                TechnicalSnapshot(
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    candle_time=item.candle_time,
                    source_label=item.source_label,
                    feature_version=item.feature_version,
                    scoring_version=item.scoring_version,
                    technical_score=item.technical_score,
                    component_scores_json=_normalize_json(item.component_scores),
                    inputs_json=_normalize_json(item.inputs),
                )
            )
        self._session.flush()
        return SnapshotPersistenceSummary(
            snapshot_kind="technical",
            rows_input=len(items),
            rows_inserted=len(items),
            rows_replaced=replaced,
        )

    def persist_sentiment_scores(
        self,
        records: Iterable[SentimentScoreRecord],
    ) -> SnapshotPersistenceSummary:
        items = list(records)
        replaced = self._replace_existing(
            SentimentSnapshot,
            [
                (item.symbol, item.asset_class, item.timeframe, item.candle_time, item.source_label)
                for item in items
            ],
        )
        for item in items:
            self._session.add(
                SentimentSnapshot(
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    candle_time=item.candle_time,
                    source_label=item.source_label,
                    input_version=item.input_version,
                    scoring_version=item.scoring_version,
                    sentiment_score=item.sentiment_score,
                    component_scores_json=_normalize_json(item.component_scores),
                    inputs_json=_normalize_json(item.inputs),
                )
            )
        self._session.flush()
        return SnapshotPersistenceSummary(
            snapshot_kind="sentiment",
            rows_input=len(items),
            rows_inserted=len(items),
            rows_replaced=replaced,
        )

    def persist_regime_detections(
        self,
        records: Iterable[RegimeDetectionRecord],
    ) -> SnapshotPersistenceSummary:
        items = list(records)
        replaced = self._replace_existing(
            RegimeSnapshot,
            [
                (item.symbol, item.asset_class, item.timeframe, item.candle_time, item.source_label)
                for item in items
            ],
        )
        for item in items:
            self._session.add(
                RegimeSnapshot(
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    candle_time=item.candle_time,
                    source_label=item.source_label,
                    technical_scoring_version=item.technical_scoring_version,
                    sentiment_scoring_version=item.sentiment_scoring_version,
                    detection_version=item.detection_version,
                    regime_label=item.regime_label,
                    regime_score=item.regime_score,
                    component_scores_json=_normalize_json(item.component_scores),
                    inputs_json=_normalize_json(item.inputs),
                )
            )
        self._session.flush()
        return SnapshotPersistenceSummary(
            snapshot_kind="regime",
            rows_input=len(items),
            rows_inserted=len(items),
            rows_replaced=replaced,
        )

    def persist_universe_candidates(
        self,
        records: Iterable[UniverseCandidateRecord],
    ) -> SnapshotPersistenceSummary:
        items = list(records)
        replaced = self._replace_existing(
            UniverseSnapshot,
            [
                (
                    item.symbol,
                    item.asset_class,
                    item.timeframe,
                    item.candle_time,
                    item.source_label,
                    item.rank,
                )
                for item in items
            ],
            include_rank=True,
        )
        for item in items:
            self._session.add(
                UniverseSnapshot(
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timeframe=item.timeframe,
                    candle_time=item.candle_time,
                    source_label=item.source_label,
                    technical_scoring_version=item.technical_scoring_version,
                    sentiment_scoring_version=item.sentiment_scoring_version,
                    regime_detection_version=item.regime_detection_version,
                    composition_version=item.composition_version,
                    rank=item.rank,
                    selected=item.selected,
                    universe_score=item.universe_score,
                    decision_label=item.decision_label,
                    component_scores_json=_normalize_json(item.component_scores),
                    inputs_json=_normalize_json(item.inputs),
                )
            )
        self._session.flush()
        return SnapshotPersistenceSummary(
            snapshot_kind="universe",
            rows_input=len(items),
            rows_inserted=len(items),
            rows_replaced=replaced,
        )

    def _replace_existing(
        self,
        model: type[TechnicalSnapshot | SentimentSnapshot | RegimeSnapshot | UniverseSnapshot],
        keys: list[tuple],
        *,
        include_rank: bool = False,
    ) -> int:
        if not keys:
            return 0

        if include_rank:
            statement = delete(model).where(
                tuple_(
                    model.symbol,
                    model.asset_class,
                    model.timeframe,
                    model.candle_time,
                    model.source_label,
                    model.rank,
                ).in_(keys)
            )
        else:
            statement = delete(model).where(
                tuple_(
                    model.symbol,
                    model.asset_class,
                    model.timeframe,
                    model.candle_time,
                    model.source_label,
                ).in_(keys)
            )
        result = self._session.execute(statement)
        return int(result.rowcount or 0)
