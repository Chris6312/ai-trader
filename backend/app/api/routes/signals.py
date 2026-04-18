
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.trading import Signal

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("/recent")
def get_recent_signals(db: Session = Depends(get_db)):

    rows = (
        db.query(Signal)
        .order_by(Signal.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "symbol": r.symbol,
            "asset_class": r.asset_class,
            "strategy": r.strategy_name,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
