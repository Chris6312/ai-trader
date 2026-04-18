from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis

from app.api import ai_research_router, execution_router, market_data_router, paper_accounts_router, risk_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.market_data.kraken import KrakenMarketDataAdapter
from app.market_data.tradier import TradierMarketDataAdapter
from app.services.market_data import MarketDataService
from app.services.market_data_runtime import MarketDataRuntimeService
from app.services.paper_accounts import PaperAccountService
from app.workers.candle_worker import CandleWorker

settings = get_settings()


def _build_market_data_runtime_service() -> MarketDataRuntimeService:
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    market_data_service = MarketDataService(redis_client=redis_client)
    return MarketDataRuntimeService(
        session_factory=SessionLocal,
        market_data_service=market_data_service,
        kraken_adapter=KrakenMarketDataAdapter(),
        tradier_adapter=TradierMarketDataAdapter(token=settings.tradier_api_token),
    )


def _build_candle_worker() -> CandleWorker:
    runtime_service = _build_market_data_runtime_service()
    return CandleWorker(
        sync_service=runtime_service,
        crypto_symbols=settings.market_data_crypto_symbols_list,
        stock_symbols=settings.market_data_stock_symbols_list,
        intervals=settings.market_data_intervals_list,
        fetch_delay_seconds=settings.market_data_fetch_delay_seconds,
    )


def _market_data_status(app: FastAPI) -> dict[str, object]:
    worker = getattr(app.state, "candle_worker", None)
    worker_task = getattr(app.state, "candle_worker_task", None)

    if worker is not None:
        status = worker.get_status()
    else:
        runtime_service = _build_market_data_runtime_service()
        status = {
            "running": False,
            "fetch_delay_seconds": settings.market_data_fetch_delay_seconds,
            "crypto_symbols": list(settings.market_data_crypto_symbols_list),
            "stock_symbols": list(settings.market_data_stock_symbols_list),
            "intervals": list(settings.market_data_intervals_list),
            "next_scheduled_run_at": None,
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_error": None,
            "last_result": None,
            "last_processed_close_by_interval": {},
            "provider_readiness": runtime_service.get_provider_readiness(),
        }

    status.update(
        {
            "worker_enabled": settings.market_data_worker_enabled,
            "worker_task_active": bool(worker_task is not None and not worker_task.done()),
        }
    )
    return status


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.paper_account_service = PaperAccountService(db_session_factory=SessionLocal)
    app.state.candle_worker = None
    app.state.candle_worker_task = None

    if settings.market_data_worker_enabled:
        worker = _build_candle_worker()
        app.state.candle_worker = worker
        app.state.candle_worker_task = asyncio.create_task(worker.run())

    try:
        yield
    finally:
        worker = getattr(app.state, "candle_worker", None)
        worker_task = getattr(app.state, "candle_worker_task", None)
        if worker is not None:
            worker.stop()
        if worker_task is not None:
            await worker_task


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_research_router)
app.include_router(paper_accounts_router)
app.include_router(market_data_router)
app.include_router(risk_router)
app.include_router(execution_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/api/market-data/worker-status")
def market_data_worker_status() -> dict[str, object]:
    return _market_data_status(app)