import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx


def make_mock_response(
    json_data: dict | None = None,
    status_code: int = 200,
    text: str = "",
    raise_for_status_error: httpx.HTTPStatusError | None = None,
    json_raises: bool = False,
) -> MagicMock:
    """httpx.Response mock factory.

    Args:
        json_data: response.json() return value
        status_code: HTTP status code
        text: response.text
        raise_for_status_error: if set, raise_for_status() raises this
        json_raises: if True, response.json() raises ValueError
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = text or str(json_data)

    if json_raises:
        mock_response.json.side_effect = ValueError("Invalid JSON")
    else:
        mock_response.json.return_value = json_data

    if raise_for_status_error:
        mock_response.raise_for_status.side_effect = raise_for_status_error
    else:
        mock_response.raise_for_status = MagicMock()

    return mock_response


def make_success_response(items: list | dict, total_count: int = 1) -> dict:
    """Create a standard 나라장터 API success response body."""
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": items,
                "totalCount": total_count,
                "numOfRows": 999,
                "pageNo": 1,
            },
        }
    }


def make_error_response(result_code: str = "99", result_msg: str = "ERROR") -> dict:
    """Create a standard 나라장터 API error response body."""
    return {
        "response": {
            "header": {"resultCode": result_code, "resultMsg": result_msg},
            "body": {},
        }
    }


def make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an httpx.HTTPStatusError for testing."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=mock_response,
    )
