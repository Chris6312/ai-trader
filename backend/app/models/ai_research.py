from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, JSON, Numeric, String, UniqueConstraint, func
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
