
import asyncio
from datetime import datetime, timezone

from app.services.candle_scheduler import next_fetch_time


class CandleWorker:
    def __init__(self, intervals=("5m","15m","1h")):
        self.intervals = intervals
        self.running = False

    async def run(self):
        self.running = True
        while self.running:
            now = datetime.now(timezone.utc)

            next_runs = [
                next_fetch_time(now, interval)
                for interval in self.intervals
            ]

            sleep_seconds = min(
                (t - now).total_seconds()
                for t in next_runs
            )

            await asyncio.sleep(max(1, sleep_seconds))

            print("fetch closed candles")
