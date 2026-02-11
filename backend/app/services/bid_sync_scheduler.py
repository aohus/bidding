import asyncio
import logging
from datetime import datetime, timedelta

from app.db.database import AsyncSessionLocal
from app.schemas.bid import BidSearchParams
from app.services.bid_data_service import bid_data_service
from app.services.narajangter import narajangter_service

logger = logging.getLogger(__name__)


class BidDataSyncScheduler:
    """입찰 데이터를 주기적으로 동기화하는 스케줄러

    동기화 대상:
    - 공고게시일시(inqryDiv=1): 과거 30일
    """

    def __init__(self):
        self.is_running = False
        self.sync_interval = 3600  # 1시간마다 증분 동기화

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("Bid data sync scheduler started")

        # 초기 전체 동기화
        try:
            await self.sync_recent_data(days=30)
        except Exception as e:
            logger.error(f"Initial sync failed: {e}")

        # 주기적 증분 동기화
        while self.is_running:
            await asyncio.sleep(self.sync_interval)
            try:
                await self.sync_recent_data(days=2)
            except Exception as e:
                logger.error(f"Incremental sync failed: {e}")

    async def stop(self):
        self.is_running = False
        logger.info("Bid data sync scheduler stopped")

    async def sync_date(self, date_str: str) -> None:
        """단일 날짜를 동기화합니다 (공고게시일시 div=1 기준)."""
        async with AsyncSessionLocal() as db:
            try:
                already = await bid_data_service.has_synced_data(
                    db, date_str, date_str
                )
            except Exception:
                already = False
            if already:
                return

            logger.info(f"Syncing {date_str}")
            bgn = f"{date_str}0000"
            end_str = f"{date_str}2359"

            # 공사/용역 공고 전체 페이지
            total_notices = 0
            page = 1
            while True:
                try:
                    params = BidSearchParams(
                        inqryDiv="1",
                        inqryBgnDt=bgn,
                        inqryEndDt=end_str,
                        numOfRows=100,
                        pageNo=page,
                    )
                    result = await narajangter_service.search_bids(params=params)
                except Exception as e:
                    logger.error(f"Failed to fetch bids {date_str} page {page}: {e}")
                    break

                if not result.items:
                    break

                await bid_data_service.save_bid_notices(db, result.items)
                total_notices += len(result.items)

                if len(result.items) < 100:
                    break
                page += 1
                await asyncio.sleep(0.5)

            page = 1
            while True:
                try:
                    params = BidSearchParams(
                        inqryDiv="1",
                        inqryBgnDt=bgn,
                        inqryEndDt=end_str,
                        numOfRows=100,
                        pageNo=page,
                    )
                    result = await narajangter_service.search_bids(params=params)
                except Exception as e:
                    logger.error(f"Failed to fetch bids {date_str} page {page}: {e}")
                    break

                if not result.items:
                    break

                await bid_data_service.save_bid_notices(db, result.items)
                total_notices += len(result.items)

                if len(result.items) < 100:
                    break
                page += 1
                await asyncio.sleep(0.5)

            # 참가가능지역
            total_regions = 0
            page = 1
            while True:
                try:
                    regions = await narajangter_service.get_prtcpt_psbl_rgn_by_date(
                        bgn, end_str, page
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch regions {date_str} page {page}: {e}")
                    break

                if not regions:
                    break

                await bid_data_service.save_prtcpt_psbl_rgns(db, regions)
                total_regions += len(regions)

                if len(regions) < 999:
                    break
                page += 1
                await asyncio.sleep(0.5)

            # 면허제한 정보
            total_license_limits = 0
            page = 1
            while True:
                try:
                    limits = await narajangter_service.get_license_limit_by_date(
                        bgn, end_str, page
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch license limits {date_str} page {page}: {e}")
                    break

                if not limits:
                    break

                await bid_data_service.save_license_limits(db, limits)
                total_license_limits += len(limits)

                if len(limits) < 999:
                    break
                page += 1
                await asyncio.sleep(0.5)

            try:
                await bid_data_service.mark_date_synced(
                    db, date_str, total_notices, total_regions, total_license_limits
                )
            except Exception as e:
                logger.warning(f"mark_date_synced failed: {e}")
            logger.info(
                f"Synced {date_str}: {total_notices} notices, "
                f"{total_regions} regions, {total_license_limits} license limits"
            )

    async def sync_recent_data(self, days: int = 30):
        """과거 N일간 공고게시일시 기준 데이터를 동기화합니다."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(
            f"Starting sync: {start_date.strftime('%Y%m%d')} ~ {end_date.strftime('%Y%m%d')}"
        )

        current = start_date
        while current <= end_date:
            await self.sync_date(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
            await asyncio.sleep(1)

        logger.info("Sync completed")


bid_sync_scheduler = BidDataSyncScheduler()
