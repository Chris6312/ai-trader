from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from redis import Redis

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import CandleInterval
from app.schemas.market_data_api import CachedQuoteOut, FetchAuditOut, MarketCandleOut
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/api/market-data", tags=["market-data"])


def _market_data_service() -> MarketDataService:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return MarketDataService(redis_client=redis_client)


@router.get("/cached-quote", response_model=CachedQuoteOut)
def get_cached_quote(symbol: str = Query(..., min_length=1)):
    service = _market_data_service()
    quote = service.get_cached_quote(symbol)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No cached quote found for {symbol}")
    return quote


@router.get("/candles", response_model=list[MarketCandleOut])
def get_recent_candles(
    symbol: str = Query(..., min_length=1),
    interval: CandleInterval = Query(...),
    limit: int = Query(50, ge=1, le=500),
):
    service = _market_data_service()
    with SessionLocal() as db:
        candles = service.list_recent_candles(db, symbol=symbol, interval=interval, limit=limit)
    return candles


@router.get("/fetch-audit", response_model=FetchAuditOut)
def get_fetch_audit():
    settings = get_settings()
    service = _market_data_service()
    return service.get_fetch_audit(worker_enabled=settings.market_data_worker_enabled)