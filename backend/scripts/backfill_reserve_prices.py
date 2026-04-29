"""1회성 reserve_price 백필 + mv REFRESH 스크립트.

사용법:
    python scripts/backfill_reserve_prices.py 20260401 20260429
    python scripts/backfill_reserve_prices.py 20260401 20260429 --max-calls 200 --no-refresh
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.reserve_price_backfill import backfill_reserve_prices  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="reserve_price one-shot backfill")
    parser.add_argument("window_from", help="시작일 YYYYMMDD")
    parser.add_argument("window_to", help="종료일 YYYYMMDD")
    parser.add_argument("--max-calls", type=int, default=None, help="API 호출 상한")
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="백필 후 mv REFRESH 생략",
    )
    parser.add_argument(
        "--no-concurrent",
        action="store_true",
        help="REFRESH MATERIALIZED VIEW (CONCURRENTLY 미사용)",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    summary = await backfill_reserve_prices(
        args.window_from,
        args.window_to,
        max_calls=args.max_calls,
        refresh_after=not args.no_refresh,
        refresh_concurrently=not args.no_concurrent,
    )
    print(
        f"Backfill complete: fetched={summary['fetched']}, "
        f"saved={summary['saved']}, errors={summary['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
