from typing import Generic, TypeVar, Optional, Any, Dict
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiError(BaseModel):
    """
    Standard error object matching the architecture specification.
    """
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    retryable: bool = Field(default=False, description="Indicates if client can retry the request")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional diagnostic details")


class ApiResponse(BaseModel, Generic[DataT]):
    """
    Standard envelope format for all API responses.
    """
    success: bool = Field(..., description="Indicates if the request was successful")
    data: Optional[DataT] = Field(default=None, description="Response payload on success")
    error: Optional[ApiError] = Field(default=None, description="Error information on failure")

    @classmethod
    def ok(cls, data: DataT) -> "ApiResponse[DataT]":
        """
        Helper factory to create a success envelope.
        """
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ) -> "ApiResponse[Any]":
        """
        Helper factory to create a failure envelope.
        """
        return cls(
            success=False,
            data=None,
            error=ApiError(code=code, message=message, retryable=retryable, details=details)
        )
