"""외부기관 공고 동기화 스케줄러.

나라장터 스케줄러(bid_sync_scheduler)와 **완전히 독립**이다 — 별도 Lock,
별도 호출 예산, 별도 실패 알림. 외부기관 수집이 느려지거나 실패해도
나라장터 동기화에 영향을 주지 않는다.

마킹 원칙은 동일하다: 윈도우 수집이 실패하면 마킹하지 않고 다음 사이클에
재시도한다. 마킹해버리면 그 구간이 영구 누락된다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.services.external_bid_service import external_bid_service
from app.services.external_sources.base import ExternalRateLimitError
from app.services.external_sources.registry import SOURCES, ExternalBidSource
from app.services.external_sources.windows import day_window, month_window

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
ALERT_THROTTLE_SECONDS = 3600


class ExternalBidSyncScheduler:
    """소스별 윈도우 기반 증분 동기화.

    전략:
      1. 최근 RECENT_DAYS 일(또는 당월)은 항상 재수집 — 늦게 등록되는 공고 커버
      2. 그 이전 구간은 미동기화 윈도우만 백필 (실행당 MAX_BACKFILL_WINDOWS)
      3. 실행당 MAX_API_CALLS_PER_RUN 로 호출 상한
      4. 모든 키 한도 소진(ExternalRateLimitError) 시 사이클 즉시 중단
    """

    SYNC_INTERVAL = 3600
    RECENT_DAYS = 3
    BACKFILL_DAYS = 30
    MAX_BACKFILL_WINDOWS = 3
    MAX_API_CALLS_PER_RUN = 60
    SOURCE_PAUSE_SECONDS = 1.0
    WINDOW_PAUSE_SECONDS = 0.5

    def __init__(self) -> None:
        self.is_running = False
        self._sync_lock = asyncio.Lock()
        self._last_alert_at: datetime | None = None
        self._failed_windows: List[str] = []

    async def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        logger.info("External bid sync scheduler started")

        try:
            await self.run_cycle()
        except Exception as exc:
            logger.error(f"Initial external sync cycle failed: {exc}")

        while self.is_running:
            await asyncio.sleep(self.SYNC_INTERVAL)
            try:
                await self.run_cycle()
            except Exception as exc:
                logger.error(f"External sync cycle failed: {exc}")

    async def stop(self) -> None:
        self.is_running = False
        logger.info("External bid sync scheduler stopped")

    async def run_cycle(self) -> int:
        """한 사이클. 사용한 API 호출 수를 반환합니다."""
        async with self._sync_lock:
            self._failed_windows = []
            api_calls = 0

            for source in SOURCES.values():
                if api_calls >= self.MAX_API_CALLS_PER_RUN:
                    logger.info(
                        "external sync: API call budget exhausted, "
                        f"skipping remaining sources (at {source.source})"
                    )
                    break
                try:
                    api_calls += await self._sync_source(source, api_calls)
                except ExternalRateLimitError as exc:
                    logger.error(
                        f"external sync aborted, all keys exhausted: {exc}"
                    )
                    self._failed_windows.append(f"(한도 소진) {exc}")
                    break
                await asyncio.sleep(self.SOURCE_PAUSE_SECONDS)

            if self._failed_windows:
                await self._send_failure_alert()
            return api_calls

    async def _sync_source(
        self, source: ExternalBidSource, api_calls_so_far: int
    ) -> int:
        """한 소스의 대상 윈도우를 순회합니다. 사용한 호출 수를 반환합니다."""
        used = 0
        for window_start, window_end, always in self._plan_windows(source):
            if api_calls_so_far + used >= self.MAX_API_CALLS_PER_RUN:
                logger.info(
                    f"external sync[{source.source}]: call budget reached"
                )
                break

            if not always:
                async with AsyncSessionLocal() as db:
                    entry = await external_bid_service.get_sync_entry(
                        db, source.source, window_start, window_end
                    )
                if entry:
                    continue

            used += await self._sync_window(source, window_start, window_end)
            await asyncio.sleep(self.WINDOW_PAUSE_SECONDS)
        return used

    def _plan_windows(
        self, source: ExternalBidSource
    ) -> Tuple[Tuple[str, str, bool], ...]:
        """(시작, 끝, 항상재수집) 윈도우 목록을 최신순으로 만듭니다.

        granularity='month' 소스(수자원)는 조회 파라미터가 월 단위라
        일별 윈도우로 돌리면 같은 달을 매일 재조회하게 된다.
        """
        now = datetime.now(KST)

        if source.granularity == "month":
            months = self._recent_months(now)
            return tuple(
                (*month_window(ym), index == 0)
                for index, ym in enumerate(months)
            )

        windows: List[Tuple[str, str, bool]] = []
        total_days = self.RECENT_DAYS + self.BACKFILL_DAYS
        backfilled = 0
        for offset in range(total_days):
            day = (now - timedelta(days=offset)).strftime("%Y%m%d")
            always = offset < self.RECENT_DAYS
            if not always:
                if backfilled >= self.MAX_BACKFILL_WINDOWS:
                    break
                backfilled += 1
            windows.append((*day_window(day), always))
        return tuple(windows)

    def _recent_months(self, now: datetime) -> Tuple[str, ...]:
        """당월 + 백필 기간이 걸치는 이전 달들 (최신순)."""
        months: List[str] = []
        cursor = now
        earliest = now - timedelta(days=self.BACKFILL_DAYS)
        while True:
            ym = cursor.strftime("%Y%m")
            if ym not in months:
                months.append(ym)
            if cursor.strftime("%Y%m") == earliest.strftime("%Y%m"):
                break
            # 전월 1일로 이동
            first_of_month = cursor.replace(day=1)
            cursor = first_of_month - timedelta(days=1)
            if len(months) > 24:  # 폭주 방지
                break
        return tuple(months)

    async def _sync_window(
        self, source: ExternalBidSource, window_start: str, window_end: str
    ) -> int:
        """단일 윈도우 수집 → 저장 → 마킹. 사용한 호출 수를 반환합니다.

        수집 실패 시 마킹하지 않는다 (다음 사이클 재시도).
        """
        label = f"{source.source} {window_start}~{window_end}"
        try:
            fetched = await source.fetch(window_start, window_end)
        except ExternalRateLimitError:
            raise
        except Exception as exc:
            logger.error(f"external sync failed [{label}]: {exc}")
            self._failed_windows.append(f"{label}: {exc}")
            # 호출 수를 알 수 없으므로 1회로 계상한다 (예산 보수적 소모).
            return 1

        try:
            async with AsyncSessionLocal() as db:
                saved_notices = await external_bid_service.save_notices(
                    db, fetched.notices
                )
                saved_results = await external_bid_service.save_results(
                    db, fetched.results
                )
                await external_bid_service.mark_window_synced(
                    db,
                    source.source,
                    window_start,
                    window_end,
                    saved_notices,
                    saved_results,
                )
        except Exception as exc:
            logger.error(f"external sync persist failed [{label}]: {exc}")
            self._failed_windows.append(f"{label} (저장 실패): {exc}")
            return fetched.api_calls

        logger.info(
            f"external sync [{label}]: {saved_notices} notices, "
            f"{saved_results} results, {fetched.api_calls} calls"
        )
        return fetched.api_calls

    async def sync_source_window(
        self, source_id: str, window_start: str, window_end: str
    ) -> int:
        """수동 트리거용: 단일 소스/윈도우 동기화 (락 포함)."""
        from app.services.external_sources.registry import get_source

        source = get_source(source_id)
        async with self._sync_lock:
            self._failed_windows = []
            calls = await self._sync_window(source, window_start, window_end)
            if self._failed_windows:
                await self._send_failure_alert()
            return calls

    async def _send_failure_alert(self) -> None:
        """실패 시 이메일 알림 (1시간에 최대 1회)."""
        now = datetime.now(KST)

        if self._last_alert_at:
            elapsed = (now - self._last_alert_at).total_seconds()
            if elapsed < ALERT_THROTTLE_SECONDS:
                logger.info(
                    f"external sync alert throttled ({int(elapsed)}s), "
                    f"{len(self._failed_windows)} failures not reported"
                )
                return

        from app.services.email_service import email_service

        to_email = settings.ALERT_EMAIL or settings.FROM_EMAIL
        if not to_email:
            logger.warning(
                "No alert email configured, skipping external sync alert"
            )
            return

        failed_list = "\n".join(f"  - {w}" for w in self._failed_windows)
        time_str = now.strftime("%Y-%m-%d %H:%M KST")
        subject = (
            f"[입찰시스템] 외부기관 동기화 실패 "
            f"({len(self._failed_windows)}건)"
        )
        html_content = f"""
<h3>외부기관 입찰 데이터 동기화 실패</h3>
<p><b>시각:</b> {time_str}</p>
<p><b>실패 윈도우 ({len(self._failed_windows)}건):</b></p>
<pre>{failed_list}</pre>
<p>다음 동기화 사이클에서 자동으로 재시도됩니다.</p>
<hr>
<p style="color: #888; font-size: 12px;">입찰 정보 시스템 자동 알림</p>
"""
        text_content = (
            f"외부기관 입찰 데이터 동기화 실패\n"
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
                logger.info(f"External sync failure alert sent to {to_email}")
            else:
                logger.warning(
                    f"Failed to send external sync alert to {to_email}"
                )
        except Exception as exc:
            logger.error(f"Error sending external sync alert: {exc}")


external_bid_sync_scheduler = ExternalBidSyncScheduler()
