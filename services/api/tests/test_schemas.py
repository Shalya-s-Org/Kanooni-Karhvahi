from app.schemas.base import ApiResponse, ApiError


def test_api_response_success_envelope():
    data = {"status": "ok", "items": [1, 2, 3]}
    res = ApiResponse.ok(data=data)
    dumped = res.model_dump()

    assert dumped["success"] is True
    assert dumped["data"] == data
    assert dumped["error"] is None


def test_api_response_failure_envelope():
    res = ApiResponse.fail(
        code="INVALID_DOCUMENT",
        message="Unsupported file type",
        retryable=False,
        details={"allowed": ["pdf", "png"]}
    )
    dumped = res.model_dump()

    assert dumped["success"] is False
    assert dumped["data"] is None
    assert dumped["error"]["code"] == "INVALID_DOCUMENT"
    assert dumped["error"]["message"] == "Unsupported file type"
    assert dumped["error"]["retryable"] is False
    assert dumped["error"]["details"]["allowed"] == ["pdf", "png"]
