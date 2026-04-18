from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AssetClass
from app.models.ai_research import RegimeSnapshot, SentimentSnapshot, TechnicalSnapshot, UniverseSnapshot
from app.schemas.ai_research_api import (
    AISnapshotInspectionOut,
    RegimeSnapshotOut,
    SentimentSnapshotOut,
    SnapshotFilterSummaryOut,
    TechnicalSnapshotOut,
    UniverseSnapshotListOut,
    UniverseSnapshotOut,
)

router = APIRouter(prefix="/api/ai", tags=["ai-research"])


@router.get("/snapshots/latest", response_model=AISnapshotInspectionOut)
def get_latest_snapshot_bundle(
    symbol: str = Query(..., min_length=1),
    asset_class: AssetClass = Query(...),
    timeframe: str = Query(..., min_length=1),
    source_label: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
) -> AISnapshotInspectionOut:
    technical_query = (
        db.query(TechnicalSnapshot)
        .filter(
            TechnicalSnapshot.symbol == symbol,
            TechnicalSnapshot.asset_class == asset_class,
            TechnicalSnapshot.timeframe == timeframe,
        )
        .order_by(desc(TechnicalSnapshot.candle_time), desc(TechnicalSnapshot.id))
    )
    if source_label is not None:
        technical_query = technical_query.filter(TechnicalSnapshot.source_label == source_label)

    technical_row = technical_query.first()
    if technical_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No technical AI snapshot found for {symbol} {asset_class.value} {timeframe}.",
        )

    aligned_source_label = technical_row.source_label
    aligned_candle_time = technical_row.candle_time

    sentiment_row = _find_single_snapshot(
        db,
        SentimentSnapshot,
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        candle_time=aligned_candle_time,
        source_label=aligned_source_label,
    )
    regime_row = _find_single_snapshot(
        db,
        RegimeSnapshot,
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        candle_time=aligned_candle_time,
        source_label=aligned_source_label,
    )
    universe_rows = (
        db.query(UniverseSnapshot)
        .filter(
            UniverseSnapshot.symbol == symbol,
            UniverseSnapshot.asset_class == asset_class,
            UniverseSnapshot.timeframe == timeframe,
            UniverseSnapshot.candle_time == aligned_candle_time,
            UniverseSnapshot.source_label == aligned_source_label,
        )
        .order_by(UniverseSnapshot.rank.asc(), UniverseSnapshot.id.asc())
        .all()
    )

    return AISnapshotInspectionOut(
        filters=SnapshotFilterSummaryOut(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            candle_time=aligned_candle_time,
            source_label=aligned_source_label,
        ),
        technical=_serialize_technical(technical_row),
        sentiment=_serialize_sentiment(sentiment_row),
        regime=_serialize_regime(regime_row),
        universe_candidates=[_serialize_universe(row) for row in universe_rows],
    )


@router.get("/universe/latest", response_model=UniverseSnapshotListOut)
def get_latest_universe_rows(
    asset_class: AssetClass | None = Query(default=None),
    timeframe: str | None = Query(default=None, min_length=1),
    source_label: str | None = Query(default=None, min_length=1),
    selected_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> UniverseSnapshotListOut:
    latest_query = db.query(UniverseSnapshot)
    if asset_class is not None:
        latest_query = latest_query.filter(UniverseSnapshot.asset_class == asset_class)
    if timeframe is not None:
        latest_query = latest_query.filter(UniverseSnapshot.timeframe == timeframe)
    if source_label is not None:
        latest_query = latest_query.filter(UniverseSnapshot.source_label == source_label)

    latest_row = latest_query.order_by(desc(UniverseSnapshot.candle_time), desc(UniverseSnapshot.id)).first()
    if latest_row is None:
        return UniverseSnapshotListOut(
            rows=[],
            returned=0,
            selected_only=selected_only,
            limit=limit,
            candle_time=None,
            timeframe=timeframe,
            source_label=source_label,
            asset_class=asset_class,
        )

    rows_query = db.query(UniverseSnapshot).filter(UniverseSnapshot.candle_time == latest_row.candle_time)
    if asset_class is not None:
        rows_query = rows_query.filter(UniverseSnapshot.asset_class == asset_class)
    else:
        rows_query = rows_query.filter(UniverseSnapshot.asset_class == latest_row.asset_class)
    if timeframe is not None:
        rows_query = rows_query.filter(UniverseSnapshot.timeframe == timeframe)
    else:
        rows_query = rows_query.filter(UniverseSnapshot.timeframe == latest_row.timeframe)
    if source_label is not None:
        rows_query = rows_query.filter(UniverseSnapshot.source_label == source_label)
    else:
        rows_query = rows_query.filter(UniverseSnapshot.source_label == latest_row.source_label)
    if selected_only:
        rows_query = rows_query.filter(UniverseSnapshot.selected.is_(True))

    rows = rows_query.order_by(UniverseSnapshot.rank.asc(), UniverseSnapshot.id.asc()).limit(limit).all()
    return UniverseSnapshotListOut(
        rows=[_serialize_universe(row) for row in rows],
        returned=len(rows),
        selected_only=selected_only,
        limit=limit,
        candle_time=latest_row.candle_time,
        timeframe=timeframe or latest_row.timeframe,
        source_label=source_label or latest_row.source_label,
        asset_class=asset_class or latest_row.asset_class,
    )


def _find_single_snapshot(
    db: Session,
    model: type[SentimentSnapshot] | type[RegimeSnapshot],
    *,
    symbol: str,
    asset_class: AssetClass,
    timeframe: str,
    candle_time,
    source_label: str,
):
    return (
        db.query(model)
        .filter(
            model.symbol == symbol,
            model.asset_class == asset_class,
            model.timeframe == timeframe,
            model.candle_time == candle_time,
            model.source_label == source_label,
        )
        .order_by(desc(model.id))
        .first()
    )


def _serialize_technical(row: TechnicalSnapshot | None) -> TechnicalSnapshotOut | None:
    if row is None:
        return None
    return TechnicalSnapshotOut(
        id=row.id,
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        feature_version=row.feature_version,
        scoring_version=row.scoring_version,
        technical_score=row.technical_score,
        component_scores=row.component_scores_json,
        inputs=row.inputs_json,
        created_at=row.created_at,
    )


def _serialize_sentiment(row: SentimentSnapshot | None) -> SentimentSnapshotOut | None:
    if row is None:
        return None
    return SentimentSnapshotOut(
        id=row.id,
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        input_version=row.input_version,
        scoring_version=row.scoring_version,
        sentiment_score=row.sentiment_score,
        component_scores=row.component_scores_json,
        inputs=row.inputs_json,
        created_at=row.created_at,
    )


def _serialize_regime(row: RegimeSnapshot | None) -> RegimeSnapshotOut | None:
    if row is None:
        return None
    return RegimeSnapshotOut(
        id=row.id,
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        technical_scoring_version=row.technical_scoring_version,
        sentiment_scoring_version=row.sentiment_scoring_version,
        detection_version=row.detection_version,
        regime_label=row.regime_label,
        regime_score=row.regime_score,
        component_scores=row.component_scores_json,
        inputs=row.inputs_json,
        created_at=row.created_at,
    )


def _serialize_universe(row: UniverseSnapshot) -> UniverseSnapshotOut:
    return UniverseSnapshotOut(
        id=row.id,
        symbol=row.symbol,
        asset_class=row.asset_class,
        timeframe=row.timeframe,
        candle_time=row.candle_time,
        source_label=row.source_label,
        technical_scoring_version=row.technical_scoring_version,
        sentiment_scoring_version=row.sentiment_scoring_version,
        regime_detection_version=row.regime_detection_version,
        composition_version=row.composition_version,
        rank=row.rank,
        selected=row.selected,
        universe_score=row.universe_score,
        decision_label=row.decision_label,
        component_scores=row.component_scores_json,
        inputs=row.inputs_json,
        created_at=row.created_at,
    )
