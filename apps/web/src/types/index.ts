export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown> | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface ComponentHealth {
  connected: boolean;
  message: string;
}

export interface HealthData {
  status: string;
  service: string;
  version: string;
  environment: string;
  database?: ComponentHealth | null;
  redis?: ComponentHealth | null;
}
