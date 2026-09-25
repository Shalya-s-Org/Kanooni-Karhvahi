import {
  ApiResponse,
  HealthData,
  DocumentUploadData,
  DocumentStatusInfo,
  DocumentMetadata,
  DocumentPagesList,
  DocumentClassificationInfo,
  DocumentEntityList,
  DocumentClauseList,
  DocumentClauseItem,
} from "../types";


export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

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

export async function uploadDocument(file: File): Promise<ApiResponse<DocumentUploadData>> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: "POST",
      body: formData,
    });
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Failed to upload file: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function intakePastedText(text: string, filename?: string): Promise<ApiResponse<DocumentUploadData>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, filename: filename || "pasted-document.txt" }),
    });
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Failed to submit text: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentStatus(documentId: string): Promise<ApiResponse<DocumentStatusInfo>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/status`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Status poll failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentMetadata(documentId: string): Promise<ApiResponse<DocumentMetadata>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Metadata fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentPages(documentId: string): Promise<ApiResponse<DocumentPagesList>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/pages`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Pages fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export function getDocumentFileUrl(documentId: string): string {
  return `${API_BASE_URL}/documents/${documentId}/file`;
}

export async function deleteDocument(documentId: string): Promise<ApiResponse<{ deleted: boolean }>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
      method: "DELETE",
    });
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Delete request failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function retryDocument(documentId: string): Promise<ApiResponse<DocumentStatusInfo>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/retry`, {
      method: "POST",
    });
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Retry request failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentClassification(documentId: string): Promise<ApiResponse<DocumentClassificationInfo>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/classification`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Classification fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentEntities(documentId: string, type?: string): Promise<ApiResponse<DocumentEntityList>> {
  try {
    const url = new URL(`${API_BASE_URL}/documents/${documentId}/entities`);
    if (type) {
      url.searchParams.set("type", type);
    }
    const res = await fetch(url.toString());
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Entities fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentClauses(documentId: string): Promise<ApiResponse<DocumentClauseList>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/clauses`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Clauses fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

export async function fetchDocumentClause(documentId: string, clauseId: string): Promise<ApiResponse<DocumentClauseItem>> {
  try {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/clauses/${clauseId}`);
    return await res.json();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: `Clause fetch failed: ${message}`,
        retryable: true,
      },
    };
  }
}

