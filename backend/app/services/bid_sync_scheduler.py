import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.db.database import AsyncSessionLocal
from app.schemas.bid import BidSearchParams
from app.services.bid_data_service import bid_data_service
from app.services.narajangter import NaraJangterService, narajangter_service

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
ALERT_THROTTLE_SECONDS = 3600  # 알림 최소 간격: 1시간


class BidDataSyncScheduler:
    """시간 윈도우 기반 증분 동기화 스케줄러

    전략:
    1. 시간별 동기화 (매시간):
       - 최근 3시간 윈도우 (현재, -1h, -2h)
       - 현재 시간: 항상 재동기화
       - 이전 시간: synced_at > 1시간이면 재동기화
       - 2시간 오버랩으로 늦게 등록되는 공고 커버

    2. 일별 백필 (매 실행 시):
       - 전일 이전 날짜 중 미동기화 건
       - 실행당 최대 MAX_BACKFILL_PER_RUN일 처리
       - 일별 윈도우 (YYYYMMDD0000 ~ YYYYMMDD2359)

    3. API 사용량 제한:
       - 페이지 간 0.5초, 윈도우 간 1초 대기
       - 실행당 최대 API 호출 수 제한
       - asyncio.Lock으로 동시 실행 방지

    4. 실패 알림:
       - 사이클 내 실패 윈도우를 모아 이메일 발송
       - 1시간에 최대 1회 (throttle)
    """

    SYNC_INTERVAL = 3600  # 1시간
    RECENT_HOURS = 3  # 최근 3시간 재동기화
    BACKFILL_DAYS = 30
    MAX_BACKFILL_PER_RUN = 5
    MAX_API_CALLS_PER_RUN = 80

    def __init__(self):
        self.is_running = False
        self._sync_lock = asyncio.Lock()
        self._last_alert_at: datetime | None = None
        self._failed_windows: list[str] = []

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("Bid data sync scheduler started")

        # 초기 실행
        try:
            await self._run_sync_cycle()
        except Exception as e:
            logger.error(f"Initial sync cycle failed: {e}")

        # 주기적 실행
        while self.is_running:
            await asyncio.sleep(self.SYNC_INTERVAL)
            try:
                await self._run_sync_cycle()
            except Exception as e:
                logger.error(f"Sync cycle failed: {e}")

    async def stop(self):
        self.is_running = False
        logger.info("Bid data sync scheduler stopped")

    async def _run_sync_cycle(self):
        """한 번의 동기화 사이클."""
        async with self._sync_lock:
            self._failed_windows = []
            api_calls = 0
            api_calls = await self._sync_recent_hours(api_calls)
            await self._backfill_past_days(api_calls)

            if self._failed_windows:
                await self._send_failure_alert()

    async def _sync_recent_hours(self, api_calls: int) -> int:
        """최근 N시간을 시간별 윈도우로 동기화합니다."""
        now = datetime.now(KST)

        for offset in range(self.RECENT_HOURS):
            if api_calls >= self.MAX_API_CALLS_PER_RUN:
                logger.info("API call limit reached, stopping recent sync")
                break

            hour_dt = now - timedelta(hours=offset)
            ts = hour_dt.strftime("%Y%m%d%H") + "00"
            end = hour_dt.strftime("%Y%m%d%H") + "59"

            async with AsyncSessionLocal() as db:
                entry = await bid_data_service.get_sync_entry(db, ts)

            if entry and offset > 0:
                age = (now - entry.synced_at.astimezone(KST)).total_seconds()
                if age < self.SYNC_INTERVAL:
                    continue

            logger.info(f"Syncing hourly window: {ts} ~ {end}")
            calls = await self._sync_window_internal(ts, end)
            api_calls += calls
            await asyncio.sleep(1)

        return api_calls

    async def _backfill_past_days(self, api_calls: int) -> int:
        """전일 이전 날짜를 일별 윈도우로 백필합니다."""
        now = datetime.now(KST)
        today = now.strftime("%Y%m%d")
        backfilled = 0

        for day_offset in range(1, self.BACKFILL_DAYS + 1):
            if backfilled >= self.MAX_BACKFILL_PER_RUN:
                break
            if api_calls >= self.MAX_API_CALLS_PER_RUN:
                logger.info("API call limit reached, stopping backfill")
                break

            date = now - timedelta(days=day_offset)
            date_str = date.strftime("%Y%m%d")

            # 오늘은 시간별 동기화가 담당
            if date_str == today:
                continue

            ts = date_str + "0000"
            end = date_str + "2359"

            async with AsyncSessionLocal() as db:
                entry = await bid_data_service.get_sync_entry(db, ts)

            if entry:
                continue

            logger.info(f"Backfilling day: {date_str}")
            calls = await self._sync_window_internal(ts, end)
            api_calls += calls
            backfilled += 1
            await asyncio.sleep(2)

        if backfilled > 0:
            logger.info(f"Backfill completed: {backfilled} days")

        return api_calls

    async def sync_window(self, window_start: str, window_end: str) -> None:
        """외부 호출용: lock 포함 윈도우 동기화."""
        async with self._sync_lock:
            await self._sync_window_internal(window_start, window_end)

    async def _sync_window_internal(
        self, window_start: str, window_end: str
    ) -> int:
        """단일 시간 윈도우를 동기화합니다. lock 없이 내부 호출용.

        Returns:
            사용된 API 호출 수
        """
        api_calls = 0
        any_success = False

        async with AsyncSessionLocal() as db:
            total_notices = 0
            total_regions = 0
            total_license_limits = 0

            # 1. 공사(contract) 공고
            count, success = await self._fetch_notices(
                db, "contract", window_start, window_end
            )
            total_notices += count
            api_calls += 1
            any_success = any_success or success

            # 2. 용역(service) 공고
            count, success = await self._fetch_notices(
                db, "service", window_start, window_end
            )
            total_notices += count
            api_calls += 1
            any_success = any_success or success

            # 3. 참가가능지역
            count, success = await self._fetch_regions(
                db, window_start, window_end
            )
            total_regions = count
            api_calls += 1
            any_success = any_success or success

            # 4. 면허제한
            count, success = await self._fetch_license_limits(
                db, window_start, window_end
            )
            total_license_limits = count
            api_calls += 1
            any_success = any_success or success

            # 5. 모든 API 실패 시 마킹하지 않음 (다음 사이클에 재시도)
            if not any_success:
                logger.warning(
                    f"All API calls failed for {window_start}~{window_end}, "
                    f"skipping mark"
                )
                self._failed_windows.append(
                    f"{window_start}~{window_end}"
                )
                return api_calls

            try:
                await bid_data_service.mark_window_synced(
                    db,
                    window_start,
                    window_end,
                    total_notices,
                    total_regions,
                    total_license_limits,
                )
            except Exception as e:
                logger.warning(f"mark_window_synced failed: {e}")

            logger.info(
                f"Synced {window_start}~{window_end}: "
                f"{total_notices} notices, {total_regions} regions, "
                f"{total_license_limits} license limits"
            )

        return api_calls

    async def _fetch_notices(
        self, db, work_type: str, bgn: str, end: str
    ) -> tuple[int, bool]:
        """공고를 페이지별로 조회하여 저장합니다. (count, success)"""
        total = 0
        page = 1
        success = False

        while True:
            try:
                params = BidSearchParams(
                    inqryDiv="1",
                    inqryBgnDt=bgn,
                    inqryEndDt=end,
                    numOfRows=100,
                    pageNo=page,
                )
                result = await narajangter_service.search_bids(
                    work_type, params
                )
                success = True
            except Exception as e:
                logger.error(
                    f"Failed to fetch {work_type} bids "
                    f"{bgn}~{end} page {page}: {e}"
                )
                break

            if not result.items:
                break

            await bid_data_service.save_bid_notices(db, result.items)
            total += len(result.items)

            if len(result.items) < 100:
                break
            page += 1
            await asyncio.sleep(0.5)

        return total, success

    async def _fetch_regions(
        self, db, bgn: str, end: str
    ) -> tuple[int, bool]:
        """참가가능지역을 페이지별로 조회하여 저장합니다."""
        total = 0
        page = 1
        success = False

        while True:
            try:
                regions = await narajangter_service.get_prtcpt_psbl_rgn_by_date(
                    bgn, end, page
                )
                success = True
            except Exception as e:
                logger.error(
                    f"Failed to fetch regions {bgn}~{end} page {page}: {e}"
                )
                break

            if not regions:
                break

            await bid_data_service.save_prtcpt_psbl_rgns(db, regions)
            total += len(regions)

            if len(regions) < NaraJangterService.MAX_PAGE_SIZE:
                break
            page += 1
            await asyncio.sleep(0.5)

        return total, success

    async def _fetch_license_limits(
        self, db, bgn: str, end: str
    ) -> tuple[int, bool]:
        """면허제한 정보를 페이지별로 조회하여 저장합니다."""
        total = 0
        page = 1
        success = False

        while True:
            try:
                limits = await narajangter_service.get_license_limit_by_date(
                    bgn, end, page
                )
                success = True
            except Exception as e:
                logger.error(
                    f"Failed to fetch license limits {bgn}~{end} page {page}: {e}"
                )
                break

            if not limits:
                break

            await bid_data_service.save_license_limits(db, limits)
            total += len(limits)

            if len(limits) < NaraJangterService.MAX_PAGE_SIZE:
                break
            page += 1
            await asyncio.sleep(0.5)

        return total, success

    async def sync_recent_data(self, days: int = 30):
        """수동 트리거용: 과거 N일 동기화."""
        async with self._sync_lock:
            self._failed_windows = []
            now = datetime.now(KST)
            api_calls = 0

            for day_offset in range(days, -1, -1):
                if api_calls >= self.MAX_API_CALLS_PER_RUN * 2:
                    logger.info("API call limit reached during manual sync")
                    break

                date = now - timedelta(days=day_offset)
                date_str = date.strftime("%Y%m%d")
                ts = date_str + "0000"
                end = date_str + "2359"

                async with AsyncSessionLocal() as db:
                    entry = await bid_data_service.get_sync_entry(db, ts)

                if entry:
                    continue

                calls = await self._sync_window_internal(ts, end)
                api_calls += calls
                await asyncio.sleep(1)

            if self._failed_windows:
                await self._send_failure_alert()

    async def _send_failure_alert(self):
        """동기화 실패 시 이메일 알림 (1시간에 최대 1회)."""
        now = datetime.now(KST)

        if self._last_alert_at:
            elapsed = (now - self._last_alert_at).total_seconds()
            if elapsed < ALERT_THROTTLE_SECONDS:
                logger.info(
                    f"Alert throttled ({int(elapsed)}s since last alert), "
                    f"{len(self._failed_windows)} failed windows not reported"
                )
                return

        from app.core.config import settings
        from app.services.email_service import email_service

        to_email = settings.ALERT_EMAIL or settings.FROM_EMAIL
        if not to_email:
            logger.warning("No alert email configured, skipping failure alert")
            return

        failed_list = "\n".join(f"  - {w}" for w in self._failed_windows)
        time_str = now.strftime("%Y-%m-%d %H:%M KST")

        subject = f"[입찰시스템] 동기화 실패 알림 ({len(self._failed_windows)}건)"
        html_content = f"""
<h3>입찰 데이터 동기화 실패</h3>
<p><b>시각:</b> {time_str}</p>
<p><b>실패 윈도우 ({len(self._failed_windows)}건):</b></p>
<pre>{failed_list}</pre>
<p>다음 동기화 사이클에서 자동으로 재시도됩니다.</p>
<hr>
<p style="color: #888; font-size: 12px;">입찰 정보 시스템 자동 알림</p>
"""
        text_content = (
            f"입찰 데이터 동기화 실패\n"
            f"시각: {time_str}\n"
            f"실패 윈도우 ({len(self._failed_windows)}건):\n"
            f"{failed_list}\n\n"
            f"다음 동기화 사이클에서 자동으로 재시도됩니다."
        )

        try:
            sent = await email_service.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )
            if sent:
                self._last_alert_at = now
                logger.info(f"Sync failure alert sent to {to_email}")
            else:
                logger.warning(f"Failed to send sync failure alert to {to_email}")
        except Exception as e:
            logger.error(f"Error sending sync failure alert: {e}")


bid_sync_scheduler = BidDataSyncScheduler()
