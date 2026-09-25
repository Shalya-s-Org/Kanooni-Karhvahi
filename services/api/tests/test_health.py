import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_envelope(async_client: AsyncClient):
    """
    Verifies that the /api/v1/health endpoint conforms strictly to the standard ApiResponse envelope.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert isinstance(payload["data"], dict)

    data = payload["data"]
    assert data["status"] == "ok"
    assert data["service"] == "kanooni-karhvahi-api"
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert "redis" in data
    assert "connected" in data["database"]
    assert "connected" in data["redis"]


@pytest.mark.asyncio
async def test_root_endpoint_disclaimer(async_client: AsyncClient):
    """
    Verifies that root endpoint renders service metadata and explicit legal disclaimer.
    """
    response = await async_client.get("/")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert "disclaimer" in payload["data"]
    assert "not a substitute" in payload["data"]["disclaimer"].lower()
