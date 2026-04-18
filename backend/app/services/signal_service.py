
import json
from datetime import datetime, UTC
from typing import Any

from sqlalchemy.orm import Session
from app.models.trading import Signal, SignalStatus


class SignalService:

    @staticmethod
    def create_signal(
        db: Session,
        symbol: str,
        asset_class: str,
        strategy: str,
        confidence: float,
        reasoning: dict[str, Any],
    ) -> Signal:

        # NOTE:
        # Signal model uses 'strategy_name' not 'strategy'
        # keep reasoning stored as JSON text for Phase 8

        signal = Signal(
            symbol=symbol,
            asset_class=asset_class,
            strategy_name=strategy,
            confidence=confidence,
            reasoning=json.dumps(reasoning, default=str),
            status=SignalStatus.NEW,
            created_at=datetime.now(UTC),
        )

        db.add(signal)
        db.commit()
        db.refresh(signal)

        return signal
