import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchDocumentStatus,
  fetchDocumentMetadata,
  fetchDocumentPages,
  getDocumentFileUrl,
  deleteDocument,
  retryDocument,
} from "../../services/api";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Trash2,
  RotateCcw,
  ArrowLeft,
  FileText,
  Eye,
} from "lucide-react";

const TERMINAL_STATUSES = new Set(["READY", "FAILED", "DELETED"]);

export const DocumentViewer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Poll status until terminal
  const statusQuery = useQuery({
    queryKey: ["doc-status", id],
    queryFn: () => fetchDocumentStatus(id!),
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 2000;
    },
    enabled: !!id,
  });

  // Metadata (fetch once status exists)
  const metaQuery = useQuery({
    queryKey: ["doc-meta", id],
    queryFn: () => fetchDocumentMetadata(id!),
    enabled: !!id,
  });

  // Pages (fetch when READY)
  const isReady = statusQuery.data?.data?.status === "READY";
  const pagesQuery = useQuery({
    queryKey: ["doc-pages", id],
    queryFn: () => fetchDocumentPages(id!),
    enabled: !!id && isReady,
  });

  const status = statusQuery.data?.data;
  const meta = metaQuery.data?.data;
  const pages = pagesQuery.data?.data?.pages ?? [];

  const handleDelete = async () => {
    if (!id) return;
    await deleteDocument(id);
    navigate("/");
  };

  const handleRetry = async () => {
    if (!id) return;
    await retryDocument(id);
    statusQuery.refetch();
  };

  const isPdf = meta?.mime_type === "application/pdf";
  const isImage = meta?.mime_type?.startsWith("image/");

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>
          <span className="text-xs text-slate-400">|</span>
          <span className="text-sm font-medium text-slate-800 truncate max-w-[300px]">
            {meta?.filename || "Document"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {status?.status === "FAILED" && status.retryable && (
            <button
              onClick={handleRetry}
              className="text-xs px-3 py-1.5 bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" /> Retry
            </button>
          )}
          <button
            onClick={handleDelete}
            className="text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 flex items-center gap-1"
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      </div>

      {/* Two-pane workspace */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-0 min-h-0">
        {/* Left: Original document */}
        <div className="border-r border-slate-200 flex flex-col min-h-0 bg-slate-50">
          <div className="px-4 py-2 border-b border-slate-200 bg-white">
            <h3 className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5" /> Original Document
            </h3>
          </div>
          <div className="flex-1 overflow-auto p-4 flex items-center justify-center">
            {!meta ? (
              <div className="text-xs text-slate-400 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading document...
              </div>
            ) : isPdf ? (
              <iframe
                src={getDocumentFileUrl(id!)}
                className="w-full h-full min-h-[500px] rounded border border-slate-200 bg-white"
                title="Original PDF"
              />
            ) : isImage ? (
              <img
                src={getDocumentFileUrl(id!)}
                alt={meta.filename}
                className="max-w-full max-h-full object-contain rounded border border-slate-200"
              />
            ) : (
              <div className="text-center text-slate-400">
                <FileText className="w-10 h-10 mx-auto mb-2" />
                <p className="text-xs">Plain text document — view extracted text on the right.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Status + Extracted text */}
        <div className="flex flex-col min-h-0 bg-white">
          <div className="px-4 py-2 border-b border-slate-200">
            <h3 className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Processing & Extracted Text
            </h3>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {/* Status card */}
            {status && (
              <div className="mb-4 p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700">Status</span>
                  <StatusBadge status={status.status} />
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div
                    className="bg-amber-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${status.progress}%` }}
                  />
                </div>
                <p className="text-[11px] text-slate-500">{status.stage}</p>

                {status.error && (
                  <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-start gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    {status.error}
                  </div>
                )}
              </div>
            )}

            {/* Metadata */}
            {meta && (
              <div className="mb-4 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                <div>
                  <span className="font-semibold">Size:</span>{" "}
                  {meta.size ? `${(meta.size / 1024).toFixed(1)} KB` : "—"}
                </div>
                <div>
                  <span className="font-semibold">Type:</span> {meta.mime_type}
                </div>
                <div>
                  <span className="font-semibold">Pages:</span> {meta.page_count}
                </div>
                <div>
                  <span className="font-semibold">Expires:</span>{" "}
                  {new Date(meta.expires_at).toLocaleString()}
                </div>
              </div>
            )}

            {/* Extracted pages */}
            {isReady && pages.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-700 border-b border-slate-100 pb-1">
                  Extracted Text ({pages.length} page{pages.length > 1 ? "s" : ""})
                </h4>
                {pages.map((p) => (
                  <div key={p.page_number} className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="bg-slate-50 px-3 py-1.5 flex items-center justify-between border-b border-slate-200">
                      <span className="text-[11px] font-semibold text-slate-600">
                        Page {p.page_number}
                      </span>
                      <div className="flex items-center gap-2 text-[10px] text-slate-400">
                        {p.ocr_used && (
                          <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium">
                            OCR {p.ocr_confidence != null ? `${(p.ocr_confidence * 100).toFixed(0)}%` : ""}
                          </span>
                        )}
                        {p.width && p.height && (
                          <span>{p.width}×{p.height}</span>
                        )}
                      </div>
                    </div>
                    <pre className="p-3 text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed max-h-[300px] overflow-auto">
                      {p.text || "(No text extracted)"}
                    </pre>
                  </div>
                ))}
              </div>
            )}

            {/* Phase 3 placeholder */}
            {isReady && (
              <div className="mt-6 p-4 bg-slate-50 border border-dashed border-slate-300 rounded-lg text-center">
                <p className="text-xs text-slate-500">
                  Legal analysis, clause simplification & Q&A will appear here in Phase 3.
                </p>
              </div>
            )}

            {/* Loading state for non-ready */}
            {!status && (
              <div className="flex items-center justify-center py-12 text-slate-400 text-xs gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading status...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode }> = {
    READY: { color: "bg-emerald-100 text-emerald-700", icon: <CheckCircle2 className="w-3 h-3" /> },
    FAILED: { color: "bg-red-100 text-red-700", icon: <AlertCircle className="w-3 h-3" /> },
    DELETED: { color: "bg-slate-200 text-slate-500", icon: <Trash2 className="w-3 h-3" /> },
  };

  const entry = map[status] ?? {
    color: "bg-amber-100 text-amber-700",
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${entry.color}`}>
      {entry.icon} {status}
    </span>
  );
}
