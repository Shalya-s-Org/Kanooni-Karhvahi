/**
 * SemanticRetrievalPanel — Phase 4 Developer Retrieval Tool
 *
 * This component is a DEVELOPMENT AND VERIFICATION TOOL.
 * It lets developers test the semantic retrieval pipeline by submitting
 * queries against an uploaded document and viewing ranked evidence chunks.
 *
 * This is NOT the final user-facing chatbot. It exists to:
 *   1. Verify the embedding → chunking → retrieval pipeline end-to-end.
 *   2. Confirm document isolation (results always belong to this document).
 *   3. Show source traceability: page number, clause ID, similarity score.
 *
 * It will be superseded by the conversational chat interface in Phase 5.
 */

import React, { useState, useRef } from "react";
import {
  Search,
  Loader2,
  AlertCircle,
  FileSearch,
  Hash,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Info,
  Cpu,
  ArrowRight,
} from "lucide-react";
import { retrieveDocumentChunks } from "../../services/api";
import { RetrievalResultItem } from "../../types";

interface SemanticRetrievalPanelProps {
  documentId: string;
  /** Called when user clicks a result — triggers page navigation in the viewer */
  onPageNavigate?: (pageNumber: number) => void;
}

interface RetrievalState {
  status: "idle" | "loading" | "success" | "error";
  results: RetrievalResultItem[];
  query: string;
  totalResults: number;
  retrievalMethod: string;
  errorMessage: string | null;
  errorCode: string | null;
}

const EXAMPLE_QUERIES = [
  "What is the payment deadline?",
  "Who are the parties to this agreement?",
  "What are the termination conditions?",
  "What is the governing law?",
  "What penalties apply for non-compliance?",
];

export const SemanticRetrievalPanel: React.FC<SemanticRetrievalPanelProps> = ({
  documentId,
  onPageNavigate,
}) => {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [state, setState] = useState<RetrievalState>({
    status: "idle",
    results: [],
    query: "",
    totalResults: 0,
    retrievalMethod: "semantic",
    errorMessage: null,
    errorCode: null,
  });

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      inputRef.current?.focus();
      return;
    }

    setState((s) => ({ ...s, status: "loading", errorMessage: null, errorCode: null }));

    const response = await retrieveDocumentChunks(documentId, trimmed, topK);

    if (response.success && response.data) {
      setState({
        status: "success",
        results: response.data.results,
        query: response.data.query,
        totalResults: response.data.total_results,
        retrievalMethod: response.data.retrieval_method,
        errorMessage: null,
        errorCode: null,
      });
    } else {
      setState({
        status: "error",
        results: [],
        query: trimmed,
        totalResults: 0,
        retrievalMethod: "semantic",
        errorMessage: response.error?.message ?? "Retrieval failed.",
        errorCode: response.error?.code ?? "UNKNOWN_ERROR",
      });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const toggleResult = (id: string) => {
    setExpandedResult((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-4">
      {/* Dev Tool Notice */}
      <div className="flex items-start gap-2.5 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800">
        <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <p className="font-bold">Phase 4 — Developer Retrieval Verification Tool</p>
          <p className="mt-0.5 text-blue-700">
            This panel tests the semantic chunking and vector retrieval pipeline.
            Results are raw evidence — no AI answer is generated here.
            Results are always scoped to <strong>this document only</strong>.
          </p>
        </div>
      </div>

      {/* Search Input */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3 shadow-xs">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What is the payment deadline?"
              className="w-full pl-9 pr-4 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-400 bg-white text-slate-800 placeholder-slate-400"
              disabled={state.status === "loading"}
              maxLength={500}
            />
          </div>

          {/* Top-K selector */}
          <div className="flex items-center gap-1.5">
            <label className="text-[11px] text-slate-500 font-medium whitespace-nowrap">Top</label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={state.status === "loading"}
              className="text-xs border border-slate-300 rounded-lg px-2 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-slate-700"
            >
              {[3, 5, 10, 15].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>

          {/* Search button */}
          <button
            onClick={handleSearch}
            disabled={state.status === "loading" || !query.trim()}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {state.status === "loading" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileSearch className="w-3.5 h-3.5" />
            )}
            {state.status === "loading" ? "Searching…" : "Search"}
          </button>
        </div>

        {/* Example queries */}
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[10px] text-slate-400 font-medium self-center">Try:</span>
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => {
                setQuery(q);
                handleSearch();
              }}
              disabled={state.status === "loading"}
              className="text-[11px] px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full transition disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {state.status === "loading" && (
        <div className="flex items-center justify-center py-10 text-slate-400 gap-2 text-sm">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Searching document for "{query}"…</span>
        </div>
      )}

      {/* Error state */}
      {state.status === "error" && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-bold text-red-800">Retrieval failed</p>
            <p className="text-red-700">{state.errorMessage}</p>
            {state.errorCode === "EMBEDDING_PROVIDER_UNAVAILABLE" && (
              <p className="text-red-600 mt-1">
                The embedding provider is not configured. Set{" "}
                <code className="bg-red-100 px-1 rounded font-mono">EMBEDDING_PROVIDER=mock</code> in your{" "}
                <code className="bg-red-100 px-1 rounded font-mono">.env</code> for local development.
              </p>
            )}
          </div>
        </div>
      )}

      {/* No results */}
      {state.status === "success" && state.results.length === 0 && (
        <div className="text-center py-10 text-slate-400 space-y-2">
          <Search className="w-8 h-8 mx-auto text-slate-300" />
          <p className="text-sm font-medium text-slate-500">No matching chunks found</p>
          <p className="text-xs">Try a different query or check that document processing completed.</p>
        </div>
      )}

      {/* Results */}
      {state.status === "success" && state.results.length > 0 && (
        <div className="space-y-3">
          {/* Results header */}
          <div className="flex items-center justify-between px-1">
            <div className="text-xs font-bold text-slate-700">
              {state.totalResults} result{state.totalResults !== 1 ? "s" : ""} for "
              <span className="italic">{state.query}</span>"
            </div>
            <MethodBadge method={state.retrievalMethod} />
          </div>

          {/* Result cards */}
          {state.results.map((result, index) => (
            <ResultCard
              key={result.chunk_id}
              result={result}
              rank={index + 1}
              isExpanded={expandedResult === result.chunk_id}
              onToggle={() => toggleResult(result.chunk_id)}
              onPageNavigate={onPageNavigate}
            />
          ))}

          {/* Traceability note */}
          <div className="flex items-center gap-2 text-[11px] text-slate-400 px-1 pt-1">
            <Cpu className="w-3.5 h-3.5" />
            <span>
              Retrieval method: <strong>{state.retrievalMethod}</strong> ·
              Results scoped to this document only ·
              Source text is verbatim — no AI modification
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Result Card ─────────────────────────────────────────────────────────────

function ResultCard({
  result,
  rank,
  isExpanded,
  onToggle,
  onPageNavigate,
}: {
  result: RetrievalResultItem;
  rank: number;
  isExpanded: boolean;
  onToggle: () => void;
  onPageNavigate?: (page: number) => void;
}) {
  const scorePercent = Math.round(result.score * 100);
  const scoreColor =
    result.score >= 0.8
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : result.score >= 0.5
      ? "text-amber-700 bg-amber-50 border-amber-200"
      : "text-slate-600 bg-slate-50 border-slate-200";

  return (
    <div className="border border-slate-200 rounded-lg bg-white overflow-hidden shadow-xs hover:border-slate-300 transition">
      {/* Card header — always visible */}
      <div
        className="px-4 py-3 flex items-start gap-3 cursor-pointer"
        onClick={onToggle}
      >
        {/* Rank badge */}
        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 text-slate-600 text-xs font-bold flex items-center justify-center mt-0.5">
          {rank}
        </div>

        {/* Text preview */}
        <div className="flex-1 min-w-0 space-y-1.5">
          <p
            className={`text-xs text-slate-700 font-serif leading-relaxed ${
              isExpanded ? "" : "line-clamp-2"
            }`}
          >
            {result.text}
          </p>

          {/* Metadata row */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Page badge — clickable */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPageNavigate?.(result.page_number);
              }}
              className="flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-full hover:bg-blue-100 transition"
            >
              <BookOpen className="w-3 h-3" />
              Page {result.page_number}
              <ArrowRight className="w-2.5 h-2.5" />
            </button>

            {/* Clause badge */}
            {result.clause_number && (
              <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 bg-slate-100 text-slate-700 border border-slate-200 rounded-full font-mono font-semibold">
                <Hash className="w-2.5 h-2.5" />
                Clause {result.clause_number}
              </span>
            )}

            {/* Similarity score */}
            <span
              className={`text-[11px] font-bold px-2 py-0.5 border rounded-full ${scoreColor}`}
            >
              {scorePercent}% match
            </span>

            {/* Retrieval method tag */}
            <span className="text-[10px] px-1.5 py-0.5 bg-slate-50 text-slate-400 border border-slate-200 rounded-full font-mono">
              {result.retrieval_method}
            </span>
          </div>
        </div>

        {/* Expand toggle */}
        <div className="text-slate-400 shrink-0 mt-1">
          {isExpanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </div>
      </div>

      {/* Expanded detail view */}
      {isExpanded && (
        <div className="border-t border-slate-100 bg-slate-50 px-4 py-3 space-y-2.5">
          {/* Full source text */}
          <div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Full Source Text (Verbatim)
            </div>
            <p className="text-xs text-slate-700 font-serif leading-relaxed whitespace-pre-wrap bg-white p-3 rounded-lg border border-slate-200">
              {result.text}
            </p>
          </div>

          {/* Traceability metadata */}
          <div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              Source Traceability
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px]">
              <TraceRow label="Document ID" value={result.document_id.slice(0, 8) + "…"} mono />
              <TraceRow label="Chunk ID" value={result.chunk_id.slice(0, 8) + "…"} mono />
              <TraceRow label="Page Number" value={`${result.page_number}`} />
              <TraceRow label="Clause Number" value={result.clause_number ?? "—"} />
              <TraceRow label="Similarity Score" value={`${(result.score * 100).toFixed(2)}%`} />
              <TraceRow label="Retrieval Method" value={result.retrieval_method} />
              <TraceRow label="Source Type" value={result.source_type} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TraceRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] text-slate-400 font-medium">{label}</span>
      <span className={`text-slate-700 font-semibold ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  const styles: Record<string, string> = {
    semantic: "bg-violet-50 text-violet-700 border-violet-200",
    lexical: "bg-amber-50 text-amber-700 border-amber-200",
    hybrid: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const style = styles[method] ?? "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 border rounded-full flex items-center gap-1 ${style}`}
    >
      <Cpu className="w-3 h-3" />
      {method} retrieval
    </span>
  );
}
