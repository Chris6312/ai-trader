from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.trading import AssetClass


class SymbolRegistry(Base):
    __tablename__ = "symbol_registry"
    __table_args__ = (
        UniqueConstraint("asset_class", "symbol", name="uq_symbol_registry_asset_class_symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_tradable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sector_or_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avg_dollar_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    history_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class HistoricalUniverseSnapshot(Base):
    __tablename__ = "historical_universe_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "decision_date",
            "asset_class",
            "symbol",
            name="uq_historical_universe_snapshot_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    registry_source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_tradable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    history_status: Mapped[str] = mapped_column(String(30), nullable=False)
    sector_or_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avg_dollar_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )




class FeatureDefinitionVersion(Base):
    __tablename__ = "feature_definition_versions"

    feature_version: Mapped[str] = mapped_column(String(30), primary_key=True)
    warmup_period: Mapped[int] = mapped_column(nullable=False)
    feature_keys_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HistoricalFeatureRow(Base):
    __tablename__ = "historical_feature_rows"
    __table_args__ = (
        UniqueConstraint(
            "decision_date",
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            "feature_version",
            name="uq_historical_feature_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    feature_version: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    values_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

class HistoricalStrategyReplay(Base):
    __tablename__ = "historical_strategy_replays"
    __table_args__ = (
        UniqueConstraint(
            "decision_date",
            "symbol",
            "asset_class",
            "timeframe",
            "strategy_name",
            "entry_candle_time",
            "replay_version",
            name="uq_historical_strategy_replay_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    replay_version: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    exit_candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    entry_confidence: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    risk_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    exit_reason: Mapped[str] = mapped_column(String(30), nullable=False)
    hold_bars: Mapped[int] = mapped_column(nullable=False)
    max_favorable_excursion: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    max_adverse_excursion: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    gross_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    strategy_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_checks_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    strategy_indicators_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    risk_rejection_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )




class BacktestingPolicyVersion(Base):
    __tablename__ = "backtesting_policy_versions"

    policy_version: Mapped[str] = mapped_column(String(30), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    replay_policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    label_version: Mapped[str] = mapped_column(String(30), nullable=False)
    evaluation_window_bars: Mapped[int] = mapped_column(nullable=False)
    success_threshold_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    max_drawdown_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    require_target_before_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regime_adjustments_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LabelPolicyVersion(Base):
    __tablename__ = "label_policy_versions"

    label_version: Mapped[str] = mapped_column(String(30), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    success_threshold_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    max_drawdown_return: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    require_target_before_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_hold_bars: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HistoricalReplayLabel(Base):
    __tablename__ = "historical_replay_labels"
    __table_args__ = (
        UniqueConstraint(
            "decision_date",
            "symbol",
            "asset_class",
            "timeframe",
            "strategy_name",
            "entry_candle_time",
            "label_version",
            name="uq_historical_replay_label_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entry_candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    replay_version: Mapped[str] = mapped_column(String(30), nullable=False)
    label_version: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    is_trade_profitable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hit_target_before_stop: Mapped[bool] = mapped_column(Boolean, nullable=False)
    follow_through_strength: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    drawdown_within_limit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    achieved_label: Mapped[bool] = mapped_column(Boolean, nullable=False)
    label_values_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TechnicalSnapshot(Base):
    __tablename__ = "ai_technical_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            name="uq_ai_technical_snapshot_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    feature_version: Mapped[str] = mapped_column(String(30), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    technical_score: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    component_scores_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    inputs_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SentimentSnapshot(Base):
    __tablename__ = "ai_sentiment_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            name="uq_ai_sentiment_snapshot_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    input_version: Mapped[str] = mapped_column(String(30), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    component_scores_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    inputs_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RegimeSnapshot(Base):
    __tablename__ = "ai_regime_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            name="uq_ai_regime_snapshot_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    technical_scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    sentiment_scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    detection_version: Mapped[str] = mapped_column(String(30), nullable=False)
    regime_label: Mapped[str] = mapped_column(String(20), nullable=False)
    regime_score: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    component_scores_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    inputs_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UniverseSnapshot(Base):
    __tablename__ = "ai_universe_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            "rank",
            name="uq_ai_universe_snapshot_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[AssetClass] = mapped_column(
        SqlEnum(AssetClass, name="asset_class_enum"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_label: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    technical_scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    sentiment_scoring_version: Mapped[str] = mapped_column(String(30), nullable=False)
    regime_detection_version: Mapped[str] = mapped_column(String(30), nullable=False)
    composition_version: Mapped[str] = mapped_column(String(30), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    universe_score: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    decision_label: Mapped[str] = mapped_column(String(20), nullable=False)
    component_scores_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    inputs_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
