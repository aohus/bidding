import pathlib

import pytest

FIXTURE_DIR = pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "external"


def load_bytes(name: str) -> bytes:
    """실제 API 응답 픽스처를 바이트로 읽습니다.

    바이트로 읽는 것이 중요하다: LH 응답은 EUC-KR 이고, 디코딩 경로 자체가
    테스트 대상이다.
    """
    return (FIXTURE_DIR / name).read_bytes()


@pytest.fixture
def fixture_bytes():
    return load_bytes
