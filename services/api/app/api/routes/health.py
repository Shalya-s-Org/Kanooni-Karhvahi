from fastapi import APIRouter, status
from app.core.config import settings
from app.schemas.base import ApiResponse
from app.schemas.health import HealthData, ComponentHealth
from app.database.session import check_database_connection
from app.api.dependencies import check_redis_connection

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=ApiResponse[HealthData],
    status_code=status.HTTP_200_OK,
    summary="Service Health Probe",
    description="Returns the operational status of the API service and its core dependencies."
)
async def get_health() -> ApiResponse[HealthData]:
    """
    Check API and downstream dependencies (PostgreSQL and Redis).
    """
    db_result = await check_database_connection()
    redis_result = await check_redis_connection()

    health_payload = HealthData(
        status="ok",
        service="kanooni-karhvahi-api",
        version=settings.VERSION,
        environment=settings.APP_ENV,
        database=ComponentHealth(
            connected=db_result["connected"],
            message=db_result["message"]
        ),
        redis=ComponentHealth(
            connected=redis_result["connected"],
            message=redis_result["message"]
        )
    )

    return ApiResponse.ok(data=health_payload)
