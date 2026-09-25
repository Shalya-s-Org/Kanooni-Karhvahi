from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    connected: bool = Field(..., description="Whether the backing component is reachable")
    message: str = Field(..., description="Status summary or diagnostic message")


class HealthData(BaseModel):
    status: str = Field(default="ok", description="Overall service status")
    service: str = Field(..., description="Name of the service")
    version: str = Field(..., description="Semantic version")
    environment: str = Field(..., description="Deployment environment")
    database: Optional[ComponentHealth] = Field(default=None, description="Database connection health")
    redis: Optional[ComponentHealth] = Field(default=None, description="Redis connection health")
