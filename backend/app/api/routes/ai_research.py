from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AssetClass
from app.models.ai_research import RegimeSnapshot, SentimentSnapshot, TechnicalSnapshot, UniverseSnapshot
from app.schemas.ai_research_api import (
    AISnapshotInspectionOut,
    MLBundleBuildOut,
    MLBundleBuildRequest,
    MLDeploymentActionOut,
    MLDeploymentActionRequest,
    MLDeploymentAuditEventOut,
    MLDeploymentFreezeRequest,
    MLDeploymentStateOut,
    MLRuntimeControlOut,
    MLTransparencyExplanationOut,
    MLTransparencyFeatureHealthPanelOut,
    MLTransparencyFeatureOut,
    MLTransparencyModelOut,
    MLTransparencyModelRegistryOut,
    MLTransparencyOverviewOut,
    MLTransparencyStrategyLearningPanelOut,
    MLTransparencyRowListOut,
    MLTransparencyRowReferenceOut,
    RegimeSnapshotOut,
    SentimentSnapshotOut,
    SnapshotFilterSummaryOut,
    TechnicalSnapshotOut,
    UniverseSnapshotListOut,
    UniverseSnapshotOut,
)
from app.schemas.stock_backfill_api import StockBackfillPolicyOut
from app.services.historical.historical_ml_deployment_safety import HistoricalMLDeploymentSafetyService
from app.services.historical.historical_ml_runtime_controls import HistoricalMLRuntimeControlService
from app.services.historical.stock_backfill_policy import StockBackfillPolicyService
from app.services.historical.historical_ml_runtime_controls_schemas import HistoricalMLRuntimeControlConfig
from app.services.historical.historical_ml_transparency import HistoricalMLTransparencyService
from app.services.historical.historical_ml_bundle_builder import HistoricalMLBundleBuilderService

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




@router.get("/backfill/stocks/policy", response_model=StockBackfillPolicyOut)
def get_stock_backfill_policy() -> StockBackfillPolicyOut:
    policy = StockBackfillPolicyService().resolve_default_policy()
    return StockBackfillPolicyOut(
        policy_version=policy.policy_version,
        policy_name=policy.policy_name,
        asset_class=policy.asset_class,
        symbol_source=policy.symbol_source,
        max_symbols_per_run=policy.max_symbols_per_run,
        max_parallel_fetches=policy.max_parallel_fetches,
        timeframes={
            timeframe: {
                "timeframe": record.timeframe,
                "lookback_days": record.lookback_days,
                "lookback_label": record.lookback_label,
            }
            for timeframe, record in policy.timeframes.items()
        },
    )



@router.post("/ml/bundles/build", response_model=MLBundleBuildOut)
def build_ml_bundle(
    body: MLBundleBuildRequest,
    db: Session = Depends(get_db),
) -> MLBundleBuildOut:
    service = HistoricalMLBundleBuilderService(db)
    try:
        summary = service.build_bundle(
            dataset_version=body.dataset_version,
            strategy_name=body.strategy_name,
            source_label=body.source_label,
            asset_class=body.asset_class,
            timeframe=body.timeframe,
            include_drift_review=body.include_drift_review,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_409_CONFLICT if detail.startswith("bundle build skipped:") else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return MLBundleBuildOut(**asdict(summary))

@router.get("/ml/deployment/state", response_model=MLDeploymentStateOut)
def get_ml_deployment_state(
    db: Session = Depends(get_db),
) -> MLDeploymentStateOut:
    service = HistoricalMLDeploymentSafetyService(db)
    return _serialize_ml_deployment_state(service.get_state())


@router.post("/ml/deployment/approve/{bundle_version}", response_model=MLDeploymentActionOut)
def approve_ml_candidate(
    bundle_version: str,
    body: MLDeploymentActionRequest,
    db: Session = Depends(get_db),
) -> MLDeploymentActionOut:
    service = HistoricalMLDeploymentSafetyService(db)
    try:
        summary = service.approve_candidate(bundle_version=bundle_version, actor=body.actor, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_ml_deployment_action(summary)


@router.post("/ml/deployment/promote/{bundle_version}", response_model=MLDeploymentActionOut)
def promote_ml_bundle(
    bundle_version: str,
    body: MLDeploymentActionRequest,
    db: Session = Depends(get_db),
) -> MLDeploymentActionOut:
    service = HistoricalMLDeploymentSafetyService(db)
    try:
        summary = service.promote_bundle(bundle_version=bundle_version, actor=body.actor, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_ml_deployment_action(summary)


@router.post("/ml/deployment/rollback", response_model=MLDeploymentActionOut)
def rollback_ml_bundle(
    body: MLDeploymentActionRequest,
    db: Session = Depends(get_db),
) -> MLDeploymentActionOut:
    service = HistoricalMLDeploymentSafetyService(db)
    try:
        summary = service.rollback_bundle(actor=body.actor, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_ml_deployment_action(summary)


@router.post("/ml/deployment/freeze/{bundle_version}", response_model=MLDeploymentActionOut)
def freeze_ml_bundle(
    bundle_version: str,
    body: MLDeploymentFreezeRequest,
    db: Session = Depends(get_db),
) -> MLDeploymentActionOut:
    service = HistoricalMLDeploymentSafetyService(db)
    try:
        summary = service.freeze_bundle(bundle_version=bundle_version, actor=body.actor, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_ml_deployment_action(summary)


@router.post("/ml/deployment/unfreeze", response_model=MLDeploymentActionOut)
def unfreeze_ml_bundle(
    body: MLDeploymentActionRequest,
    db: Session = Depends(get_db),
) -> MLDeploymentActionOut:
    service = HistoricalMLDeploymentSafetyService(db)
    try:
        summary = service.unfreeze_bundle(actor=body.actor, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_ml_deployment_action(summary)


@router.get("/ml/runtime", response_model=MLRuntimeControlOut)
def get_ml_runtime_controls(
    bundle_version: str = Query(..., min_length=1),
    strategy_name: str = Query(..., min_length=1),
    requested_mode: str = Query(default="active_rank_only", pattern="^(disabled|shadow|active_rank_only)$"),
    stale_after_days: int = Query(default=14, ge=1, le=365),
    minimum_validation_metric: float | None = Query(default=None, ge=0.0, le=1.0),
    validation_metric_key: str = Query(default="roc_auc", min_length=1),
    required_features: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MLRuntimeControlOut:
    service = HistoricalMLRuntimeControlService(
        db,
        config=HistoricalMLRuntimeControlConfig(
            requested_mode=requested_mode,
            stale_after_days=stale_after_days,
            minimum_validation_metric=minimum_validation_metric,
            validation_metric_key=validation_metric_key,
            required_feature_keys=list(required_features or []),
        ),
    )
    summary = service.evaluate_runtime_controls(
        bundle_version=bundle_version,
        strategy_name=strategy_name,
    )
    return MLRuntimeControlOut(**asdict(summary))


@router.get("/ml/models", response_model=MLTransparencyModelRegistryOut)
def get_ml_model_registry(
    db: Session = Depends(get_db),
) -> MLTransparencyModelRegistryOut:
    service = HistoricalMLTransparencyService(db)
    rows = service.list_models()
    return MLTransparencyModelRegistryOut(
        rows=[_serialize_ml_model(row) for row in rows],
        returned=len(rows),
    )


@router.get("/ml/overview", response_model=MLTransparencyOverviewOut)
def get_ml_transparency_overview(
    bundle_version: str = Query(..., min_length=1),
    row_limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
) -> MLTransparencyOverviewOut:
    service = HistoricalMLTransparencyService(db)
    try:
        overview = service.get_overview(bundle_version=bundle_version, row_limit=row_limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyOverviewOut(
        model=_serialize_ml_model(overview.model),
        lineage=overview.lineage,
        training_metrics=overview.training_metrics,
        global_feature_importance=[_serialize_ml_feature(item) for item in overview.global_feature_importance],
        regime_feature_importance=[_serialize_ml_feature(item) for item in overview.regime_feature_importance],
        drift_signals=[_serialize_ml_feature(item) for item in overview.drift_signals],
        health=overview.health,
        sample_rows=[_serialize_ml_row_reference(item) for item in overview.sample_rows],
    )


@router.get("/ml/rows", response_model=MLTransparencyRowListOut)
def get_ml_historical_rows(
    bundle_version: str = Query(..., min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MLTransparencyRowListOut:
    service = HistoricalMLTransparencyService(db)
    try:
        rows = service.list_historical_rows(bundle_version=bundle_version, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyRowListOut(
        rows=[_serialize_ml_row_reference(item) for item in rows],
        returned=len(rows),
    )


@router.get("/ml/inspection/strategy", response_model=MLTransparencyStrategyLearningPanelOut)
def get_ml_strategy_learning_panel(
    bundle_version: str = Query(..., min_length=1),
    requested_mode: str = Query(default="active_rank_only", pattern="^(disabled|shadow|active_rank_only)$"),
    stale_after_days: int = Query(default=14, ge=1, le=365),
    minimum_validation_metric: float | None = Query(default=None, ge=0.0, le=1.0),
    validation_metric_key: str = Query(default="roc_auc", min_length=1),
    db: Session = Depends(get_db),
) -> MLTransparencyStrategyLearningPanelOut:
    service = HistoricalMLTransparencyService(db)
    runtime_service = HistoricalMLRuntimeControlService(
        db,
        config=HistoricalMLRuntimeControlConfig(
            requested_mode=requested_mode,
            stale_after_days=stale_after_days,
            minimum_validation_metric=minimum_validation_metric,
            validation_metric_key=validation_metric_key,
        ),
    )
    try:
        overview = service.get_overview(bundle_version=bundle_version, row_limit=5)
        runtime_control = runtime_service.evaluate_runtime_controls(
            bundle_version=bundle_version,
            strategy_name=overview.model.strategy_name,
        )
        panel = service.get_strategy_learning_panel(
            bundle_version=bundle_version,
            runtime_control=runtime_control,
            row_limit=5,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyStrategyLearningPanelOut(
        bundle_version=panel.bundle_version,
        model_version=panel.model_version,
        dataset_version=panel.dataset_version,
        strategy_name=panel.strategy_name,
        runtime_control=MLRuntimeControlOut(**asdict(panel.runtime_control)) if panel.runtime_control is not None else None,
        summary=panel.summary,
        global_feature_importance=[_serialize_ml_feature(item) for item in panel.global_feature_importance],
        regime_feature_importance=[_serialize_ml_feature(item) for item in panel.regime_feature_importance],
        drift_signals=[_serialize_ml_feature(item) for item in panel.drift_signals],
        highlighted_rows=[_serialize_ml_row_reference(item) for item in panel.highlighted_rows],
    )


@router.get("/ml/inspection/feature-health", response_model=MLTransparencyFeatureHealthPanelOut)
def get_ml_feature_health_panel(
    bundle_version: str = Query(..., min_length=1),
    requested_mode: str = Query(default="active_rank_only", pattern="^(disabled|shadow|active_rank_only)$"),
    stale_after_days: int = Query(default=14, ge=1, le=365),
    minimum_validation_metric: float | None = Query(default=None, ge=0.0, le=1.0),
    validation_metric_key: str = Query(default="roc_auc", min_length=1),
    db: Session = Depends(get_db),
) -> MLTransparencyFeatureHealthPanelOut:
    service = HistoricalMLTransparencyService(db)
    runtime_service = HistoricalMLRuntimeControlService(
        db,
        config=HistoricalMLRuntimeControlConfig(
            requested_mode=requested_mode,
            stale_after_days=stale_after_days,
            minimum_validation_metric=minimum_validation_metric,
            validation_metric_key=validation_metric_key,
        ),
    )
    try:
        overview = service.get_overview(bundle_version=bundle_version, row_limit=5)
        runtime_control = runtime_service.evaluate_runtime_controls(
            bundle_version=bundle_version,
            strategy_name=overview.model.strategy_name,
        )
        panel = service.get_feature_health_panel(
            bundle_version=bundle_version,
            runtime_control=runtime_control,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyFeatureHealthPanelOut(
        bundle_version=panel.bundle_version,
        model_version=panel.model_version,
        dataset_version=panel.dataset_version,
        strategy_name=panel.strategy_name,
        runtime_control=MLRuntimeControlOut(**asdict(panel.runtime_control)) if panel.runtime_control is not None else None,
        validation_summary=panel.validation_summary,
        drift_summary=panel.drift_summary,
        global_feature_leaders=[_serialize_ml_feature(item) for item in panel.global_feature_leaders],
        regime_feature_leaders=[_serialize_ml_feature(item) for item in panel.regime_feature_leaders],
        overlapping_feature_keys=panel.overlapping_feature_keys,
    )


@router.get("/ml/explanations/by-symbol-date", response_model=MLTransparencyExplanationOut)
def get_ml_historical_explanation_by_symbol_date(
    bundle_version: str = Query(..., min_length=1),
    symbol: str = Query(..., min_length=1),
    decision_date: str = Query(..., min_length=10, max_length=10),
    db: Session = Depends(get_db),
) -> MLTransparencyExplanationOut:
    service = HistoricalMLTransparencyService(db)
    try:
        explanation = service.explain_symbol_on_decision_date(
            bundle_version=bundle_version,
            symbol=symbol,
            decision_date=decision_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyExplanationOut(
        bundle_version=explanation.bundle_version,
        model_version=explanation.model_version,
        dataset_version=explanation.dataset_version,
        strategy_name=explanation.strategy_name,
        row=_serialize_ml_row_reference(explanation.row),
        score=explanation.score,
        probability=explanation.probability,
        confidence=explanation.confidence,
        baseline_expectation=explanation.baseline_expectation,
        positive_contributors=[_serialize_ml_feature(item) for item in explanation.positive_contributors],
        negative_contributors=[_serialize_ml_feature(item) for item in explanation.negative_contributors],
        feature_snapshot=explanation.feature_snapshot,
        skipped_reason=explanation.skipped_reason,
    )


@router.get("/ml/explanations/historical", response_model=MLTransparencyExplanationOut)
def get_ml_historical_explanation(
    bundle_version: str = Query(..., min_length=1),
    row_key: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> MLTransparencyExplanationOut:
    service = HistoricalMLTransparencyService(db)
    try:
        explanation = service.explain_historical_row(bundle_version=bundle_version, row_key=row_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MLTransparencyExplanationOut(
        bundle_version=explanation.bundle_version,
        model_version=explanation.model_version,
        dataset_version=explanation.dataset_version,
        strategy_name=explanation.strategy_name,
        row=_serialize_ml_row_reference(explanation.row),
        score=explanation.score,
        probability=explanation.probability,
        confidence=explanation.confidence,
        baseline_expectation=explanation.baseline_expectation,
        positive_contributors=[_serialize_ml_feature(item) for item in explanation.positive_contributors],
        negative_contributors=[_serialize_ml_feature(item) for item in explanation.negative_contributors],
        feature_snapshot=explanation.feature_snapshot,
        skipped_reason=explanation.skipped_reason,
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


def _serialize_ml_deployment_event(row) -> MLDeploymentAuditEventOut:
    return MLDeploymentAuditEventOut(**asdict(row))


def _serialize_ml_deployment_state(row) -> MLDeploymentStateOut:
    return MLDeploymentStateOut(
        active_bundle_version=row.active_bundle_version,
        approved_candidate_versions=list(row.approved_candidate_versions),
        frozen_bundle_version=row.frozen_bundle_version,
        freeze_reason=row.freeze_reason,
        change_history=[_serialize_ml_deployment_event(item) for item in row.change_history],
    )


def _serialize_ml_deployment_action(row) -> MLDeploymentActionOut:
    return MLDeploymentActionOut(
        state=_serialize_ml_deployment_state(row.state),
        event=_serialize_ml_deployment_event(row.event),
    )


def _serialize_ml_model(row) -> MLTransparencyModelOut:
    return MLTransparencyModelOut(**asdict(row))


def _serialize_ml_feature(row) -> MLTransparencyFeatureOut:
    return MLTransparencyFeatureOut(**asdict(row))


def _serialize_ml_row_reference(row) -> MLTransparencyRowReferenceOut:
    return MLTransparencyRowReferenceOut(**asdict(row))
