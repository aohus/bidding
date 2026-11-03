from app.core.rate_limit import SlidingWindowRateLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(max_requests=3, window=60, max_keys=10):
    clock = Clock()
    return SlidingWindowRateLimiter(max_requests, window, max_keys, clock), clock


def test_allows_up_to_limit_then_blocks():
    rl, _ = make()
    assert [rl.allow("u") for _ in range(4)] == [True, True, True, False]


def test_blocked_requests_are_not_recorded():
    rl, clock = make()
    for _ in range(5):
        rl.allow("u")
    clock.t += 60.01
    assert rl.allow("u") is True  # 차단된 요청이 윈도우를 연장하지 않는다


def test_window_slides():
    rl, clock = make()
    rl.allow("u")
    clock.t += 30
    rl.allow("u")
    rl.allow("u")
    assert rl.allow("u") is False
    clock.t += 30.01  # 첫 요청만 만료
    assert rl.allow("u") is True
    assert rl.allow("u") is False


def test_keys_are_independent():
    rl, _ = make(max_requests=1)
    assert rl.allow("a") and rl.allow("b")
    assert not rl.allow("a")


def test_key_table_is_bounded():
    rl, _ = make(max_requests=1, max_keys=5)
    for i in range(50):
        rl.allow(f"u{i}")
    assert len(rl._hits) <= 5


def test_expired_keys_are_evicted_first():
    rl, clock = make(max_requests=1, max_keys=2)
    rl.allow("old")
    clock.t += 100
    rl.allow("fresh")
    rl.allow("new")  # 가득 참 -> 만료된 old 제거
    assert "old" not in rl._hits and "fresh" in rl._hits


def test_reset():
    rl, _ = make(max_requests=1)
    rl.allow("u")
    rl.reset()
    assert rl.allow("u")
