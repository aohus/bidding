"""data.go.kr 서비스키 로테이션 상태기계.

나라장터 클라이언트와 외부기관 클라이언트가 동일한 키 풀을 공유하므로
로테이션 규칙(순차 전환 + 24h 후 첫 키 복귀)도 한 곳에서만 관리한다.
HTTP 나 응답 포맷 해석은 포함하지 않는다 — 호출자가 포맷별로 판단한 뒤
rotate() 를 호출한다.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# 마지막 로테이션 후 이 시간이 지나면 첫 키로 복귀 (일일 한도 리셋 반영).
KEY_RESET_SECONDS = 24 * 3600


class NoServiceKeyError(Exception):
    """사용 가능한 서비스키가 하나도 설정되지 않은 경우."""


class ServiceKeyRotator:
    """순서가 있는 서비스키 풀의 현재 위치를 관리합니다."""

    def __init__(self, keys: Sequence[str]) -> None:
        self._keys: List[str] = list(keys)
        self._active_idx: int = 0
        self._rotated_at: Optional[datetime] = None

    @property
    def key_count(self) -> int:
        return len(self._keys)

    @property
    def active_idx(self) -> int:
        return self._active_idx

    @property
    def rotated_at(self) -> Optional[datetime]:
        return self._rotated_at

    def active_key(self) -> str:
        if not self._keys:
            raise NoServiceKeyError(
                "서비스키가 설정되지 않았습니다 "
                "(NARAJANGTER_SERVICE_KEY 를 확인하세요)"
            )
        return self._keys[self._active_idx]

    def maybe_reset(self) -> None:
        """마지막 로테이션 후 24h 경과 시 첫 키로 복귀합니다."""
        if self._active_idx == 0 or self._rotated_at is None:
            return
        elapsed = (datetime.now(timezone.utc) - self._rotated_at).total_seconds()
        if elapsed >= KEY_RESET_SECONDS:
            logger.info(
                f"service key: {int(elapsed)}s since last rotation, "
                f"resetting to key index 0"
            )
            self._active_idx = 0
            self._rotated_at = None

    def rotate(self) -> bool:
        """다음 키로 전환합니다. 더 이상 사용 가능한 키가 없으면 False."""
        if self._active_idx + 1 >= len(self._keys):
            return False
        self._active_idx += 1
        self._rotated_at = datetime.now(timezone.utc)
        logger.warning(
            f"service key: rotating to key index {self._active_idx}"
            f"/{len(self._keys) - 1}"
        )
        return True
