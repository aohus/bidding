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


def make_service_error_response(
    result_code: str = "07", result_msg: str = "입력범위값 초과 에러"
) -> dict:
    """조달청 서비스 자체 파라미터 검증 에러 봉투.

    실제 응답 예: 조회기간을 1개월 초과로 요청했을 때.
    HTTP 200 으로 오지만 'response' 키가 없다.
    """
    return {
        "nkoneps.com.response.ResponseError": {
            "header": {"resultCode": result_code, "resultMsg": result_msg},
        }
    }


def make_gateway_error_response(
    return_reason_code: str = "22",
    err_msg: str = "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
    return_auth_msg: str = "서비스 요청 제한 횟수 초과",
) -> dict:
    """data.go.kr 게이트웨이 에러 봉투.

    일일 활용건수 초과(22)와 미등록 서비스키(30)가 이 형태로 온다.
    22 는 HTTP 429 가 아니라 이 봉투로 오므로 별도 처리가 필요하다.
    """
    return {
        "OpenAPI_ServiceResponse": {
            "cmmMsgHeader": {
                "errMsg": err_msg,
                "returnAuthMsg": return_auth_msg,
                "returnReasonCode": return_reason_code,
            }
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
