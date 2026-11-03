import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.db.database import AsyncSessionLocal
from app.models.user import User, UserPreference
from app.schemas.bid import BidSearchParams
from app.services.bid_data_service import bid_data_service
from app.services.email_service import email_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# rgst_dt 는 KST(YYYYMMDDHHMM) 로 저장되므로 윈도우도 KST 로 계산한다.
KST = timezone(timedelta(hours=9))
DATE_FORMAT = "%Y%m%d%H%M"

MAX_RESULTS = 100
MAX_LOOKBACK = timedelta(days=7)
# rgst_dt 하한을 직전 알림보다 이만큼 더 과거로 잡는다. 공고가 rgst_dt 보다
# 늦게 동기화되는 경우를 커버한다 (실제 중복 방지는 created_at 이 담당).
LATE_SYNC_MARGIN = timedelta(days=1)
MAX_LIST_ITEMS = 20
MAX_ITEM_LENGTH = 50
FREQUENCY_INTERVALS = {
    "realtime": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}

# 저장 조건의 불리언 플래그 (BidSearchParams 필드명과 동일한 키)
BOOL_KEYS = (
    "useLocationFilter",
    "incntvRgnOnly",
    "jntcontrctDutyRgnOnly",
    "includeSubsiCnstty",
)


def _str_list(value: Any) -> Optional[str]:
    """문자열 또는 문자열 리스트 -> 쉼표 구분 문자열. 유효 항목이 없으면 None."""
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = [v for v in value if isinstance(v, str)]
    else:
        return None
    cleaned = [i.strip()[:MAX_ITEM_LENGTH] for i in items if i.strip()]
    cleaned = cleaned[:MAX_LIST_ITEMS]
    return ",".join(cleaned) or None


def _price(value: Any) -> Optional[str]:
    """숫자 문자열/정수만 허용 (bool 제외)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return str(value)
    if isinstance(value, str) and value.strip().isdigit():
        return value.strip()
    return None


def _exclude_closed(value: Any) -> Optional[str]:
    if value is True or value == "Y":
        return "Y"
    if value is False or value == "N":
        return "N"
    return None


def build_search_params(
    conditions: Any, window_start: str, window_end: str
) -> BidSearchParams:
    """저장된 search_conditions 를 화이트리스트 기반으로 BidSearchParams 로 변환.

    프론트(SearchForm.getCurrentFilters)가 저장하는 키:
      regions[] -> prtcptLmtRgnNm, industries[] -> indstrytyNm,
      priceStart/priceEnd -> presmptPrceBgn/End, excludeClosed -> bidClseExcpYn,
      cnstrtsiteRgnNm, useLocationFilter 및 신규 플래그 3종(키 이름 동일).
    알 수 없는 키는 무시하고, 기간/페이지 크기는 저장값으로 덮어쓸 수 없다.
    알림은 '새 공고' 기준이므로 항상 공고게시일시(inqryDiv=1)로 조회한다.
    """
    cond: Dict[str, Any] = conditions if isinstance(conditions, dict) else {}
    flags = {k: True for k in BOOL_KEYS if cond.get(k) is True}
    site = cond.get("cnstrtsiteRgnNm")
    return BidSearchParams(
        inqryDiv="1",
        inqryBgnDt=window_start,
        inqryEndDt=window_end,
        prtcptLmtRgnNm=_str_list(cond.get("regions")),
        cnstrtsiteRgnNm=site.strip() or None if isinstance(site, str) else None,
        indstrytyNm=_str_list(cond.get("industries")),
        presmptPrceBgn=_price(cond.get("priceStart")),
        presmptPrceEnd=_price(cond.get("priceEnd")),
        bidClseExcpYn=_exclude_closed(cond.get("excludeClosed")),
        orderBy="rgstDt",
        orderDir="desc",
        numOfRows=MAX_RESULTS,
        pageNo=1,
        **flags,
    )


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class NotificationScheduler:
    """저장된 검색 조건에 맞는 신규 공고를 DB 에서 찾아 이메일로 알린다."""

    def __init__(self):
        self.is_running = False
        self.check_interval = 3600  # Check every hour

    async def start(self):
        if self.is_running:
            return

        self.is_running = True
        logger.info("Notification scheduler started")

        while self.is_running:
            try:
                await self.check_and_notify()
            except Exception:
                logger.exception("Error in notification scheduler")

            await asyncio.sleep(self.check_interval)

    async def stop(self):
        self.is_running = False
        logger.info("Notification scheduler stopped")

    async def check_and_notify(self):
        logger.info("Checking for new bid notices")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User, UserPreference)
                .join(UserPreference, User.user_id == UserPreference.user_id)
                .where(UserPreference.email_notifications_enabled == True)  # noqa: E712
            )
            users_with_prefs = result.all()

            for user, preference in users_with_prefs:
                try:
                    await self.notify_user(db, user, preference)
                except Exception:
                    logger.exception("Failed to notify user %s", user.username)
                    await db.rollback()

    async def notify_user(
        self,
        db: AsyncSession,
        user: User,
        preference: UserPreference,
        now: Optional[datetime] = None,
    ) -> bool:
        """사용자의 신규 매칭 공고를 발송한다. 발송했으면 True.

        중복 방지는 공고 삽입 시각(BidNotice.created_at) 기준이다.
        rgst_dt 기준 윈도우만 쓰면 rgst_dt 이후에 늦게 동기화된 공고가 영영
        발송되지 않는다. 그래서:
          - rgst_dt 범위 = [직전 알림 - 1일(첫 실행은 빈도 기준), 현재]
          - created_at > 직전 알림 시각 (첫 실행은 None -> 빈도 기반 시작)
          - created_at 오름차순 상위 MAX_RESULTS 건만 발송하고,
            last_notification_at 을 '발송한 마지막 공고의 created_at' 으로 둔다.
            100건 초과분은 다음 실행이 이어서 처리한다 (조용한 누락 없음).
        마이그레이션 직후 기존 행의 created_at 은 마이그레이션 시각이므로, 첫
        실행에서 [직전 알림 - 1일, 현재] 의 rgst_dt 범위 공고가 한 번 재발송될
        수 있다 (rgst_dt 하한이 이 일회성 폭주를 제한한다).
        발송 실패 시 상태를 바꾸지 않아 다음 주기에 같은 구간을 재시도한다.
        """
        if not preference.search_conditions:
            return False

        now_kst = (now or datetime.now(KST)).astimezone(KST)
        frequency = preference.notification_frequency or "daily"
        if not self._should_notify(preference, frequency, now_kst):
            return False

        current_minute = now_kst.replace(second=0, microsecond=0)
        window_start = self._window_start(preference, frequency, now_kst)
        created_after = (
            _as_aware(preference.last_notification_at)
            if preference.last_notification_at
            else None
        )

        params = build_search_params(
            preference.search_conditions,
            window_start.strftime(DATE_FORMAT),
            current_minute.strftime(DATE_FORMAT),
        )
        response = await bid_data_service.search_from_db(
            db,
            params,
            user_id=user.user_id,
            created_after=created_after,
            order_by_created_at=True,
        )
        if not response.items:
            return False
        if response.totalCount > len(response.items):
            logger.warning(
                "User %s: %d matches, notifying oldest %d now, rest next run",
                user.username, response.totalCount, len(response.items),
            )

        sent = await email_service.send_bid_notification(
            to_email=user.email,
            username=user.username,
            bid_notices=response.items,
        )
        if not sent:
            logger.warning("Notification email failed for user %s", user.username)
            return False

        last_created = await bid_data_service.max_created_at(
            db, [(i.bidNtceNo, i.bidNtceOrd) for i in response.items]
        )
        preference.last_notification_at = last_created or current_minute
        await db.commit()
        logger.info(
            "Sent notification to %s: %d new bids", user.username, len(response.items)
        )
        return True

    @staticmethod
    def _window_start(
        preference: UserPreference, frequency: str, now_kst: datetime
    ) -> datetime:
        earliest = (now_kst - MAX_LOOKBACK).replace(second=0, microsecond=0)
        if preference.last_notification_at:
            start = (
                _as_aware(preference.last_notification_at).astimezone(KST)
                - LATE_SYNC_MARGIN
            )
        else:
            interval = FREQUENCY_INTERVALS.get(frequency, timedelta(days=1))
            start = now_kst - interval
        return max(start.replace(second=0, microsecond=0), earliest)

    def _should_notify(
        self,
        preference: UserPreference,
        frequency: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """빈도(realtime/daily/weekly)와 직전 알림 시각 기준 발송 시점 여부."""
        if not preference.last_notification_at:
            return True

        interval = FREQUENCY_INTERVALS.get(frequency)
        if interval is None:
            return False

        now = now or datetime.now(timezone.utc)
        elapsed = _as_aware(now) - _as_aware(preference.last_notification_at)
        return elapsed >= interval


# Singleton instance
notification_scheduler = NotificationScheduler()
