from datetime import datetime, timedelta, timezone

import pytest

from app.services.service_key_rotator import (
    KEY_RESET_SECONDS,
    NoServiceKeyError,
    ServiceKeyRotator,
)


@pytest.fixture
def single():
    return ServiceKeyRotator(["key1"])


@pytest.fixture
def multi():
    return ServiceKeyRotator(["key1", "key2", "key3"])


class TestActiveKey:
    def test_starts_at_first_key(self, multi):
        assert multi.active_key() == "key1"
        assert multi.active_idx == 0

    def test_empty_pool_raises(self):
        with pytest.raises(NoServiceKeyError):
            ServiceKeyRotator([]).active_key()

    def test_pool_is_copied_not_aliased(self):
        keys = ["a", "b"]
        rotator = ServiceKeyRotator(keys)
        keys.append("c")
        assert rotator.key_count == 2


class TestRotate:
    def test_advances_to_next_key(self, multi):
        assert multi.rotate() is True
        assert multi.active_key() == "key2"

    def test_returns_false_when_exhausted(self, single):
        assert single.rotate() is False
        assert single.active_key() == "key1"

    def test_records_rotation_timestamp(self, multi):
        assert multi.rotated_at is None
        multi.rotate()
        assert multi.rotated_at is not None

    def test_exhausts_after_all_keys(self, multi):
        assert multi.rotate() is True
        assert multi.rotate() is True
        assert multi.rotate() is False
        assert multi.active_idx == 2


class TestReset:
    def test_resets_to_first_key_after_window(self, multi):
        multi.rotate()
        multi._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS + 60
        )

        multi.maybe_reset()

        assert multi.active_idx == 0
        assert multi.rotated_at is None

    def test_does_not_reset_before_window(self, multi):
        multi.rotate()
        multi._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS - 60
        )

        multi.maybe_reset()

        assert multi.active_idx == 1

    def test_noop_when_already_on_first_key(self, multi):
        multi.maybe_reset()
        assert multi.active_idx == 0
