"""의존성 없는 인프로세스 슬라이딩 윈도우 레이트 리미터.

프로세스(워커) 단위 제한이다. 다중 워커에서는 워커 수만큼 한도가 늘어나므로
업스트림 쿼터 보호용 완충 장치로만 쓰고, 정밀한 제한이 필요하면 Redis 등을 쓴다.
"""
import time
from collections import deque
from typing import Callable, Deque, Dict, Hashable


class SlidingWindowRateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._hits: Dict[Hashable, Deque[float]] = {}

    def allow(self, key: Hashable) -> bool:
        """요청을 허용하면 기록하고 True, 한도 초과면 기록 없이 False."""
        now = self._clock()
        cutoff = now - self.window_seconds
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.max_keys:
                self._evict(cutoff)
            hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def _evict(self, cutoff: float) -> None:
        """만료된 키를 제거하고, 그래도 가득 차면 가장 오래된 키를 버린다."""
        for k in [k for k, h in self._hits.items() if not h or h[-1] <= cutoff]:
            del self._hits[k]
        if len(self._hits) >= self.max_keys:
            del self._hits[next(iter(self._hits))]

    def reset(self) -> None:
        self._hits.clear()
