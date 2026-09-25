import { ApiResponse, HealthData } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export async function fetchHealth(): Promise<ApiResponse<HealthData>> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) {
      return {
        success: false,
        data: null,
        error: {
          code: `HTTP_${res.status}`,
          message: `Health check failed with status ${res.status}`,
          retryable: true,
        },
      };
    }
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Could not reach backend API at ${API_BASE_URL}: ${message}`,
        retryable: true,
      },
    };
  }
}
