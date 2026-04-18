
import json
from datetime import datetime
from typing import Any

from app.models.trading import Signal, SignalStatus
from sqlalchemy.orm import Session

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

        signal = Signal(
            symbol=symbol,
            asset_class=asset_class,
            strategy=strategy,
            confidence=confidence,
            reasoning=json.dumps(reasoning, default=str),
            status=SignalStatus.NEW,
            created_at=datetime.utcnow(),
        )

        db.add(signal)
        db.commit()
        db.refresh(signal)

        return signal
