
from app.workers.candle_worker import CandleWorker


def test_worker_init():
    worker = CandleWorker()
    assert worker is not None
