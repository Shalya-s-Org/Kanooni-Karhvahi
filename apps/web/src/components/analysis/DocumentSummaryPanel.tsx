import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchDocumentSummary,
  generateDocumentSummary,
} from "../../services/api";
import { SafetyDisclaimer } from "./SafetyDisclaimer";
import { EvidenceReference } from "./EvidenceReference";
import { CheckSignal, KeyPoint } from "../../types";
import {
  Sparkles,
  Loader2,
  AlertTriangle,
  Info,
  Calendar,
  IndianRupee,
  Users,
  CheckCircle,
  HelpCircle,
  RefreshCw,
  FileText,
  ShieldCheck,
} from "lucide-react";

interface DocumentSummaryPanelProps {
  documentId: string;
  isReady: boolean;
  onPageNavigate: (page: number) => void;
  onClauseSelect?: (clauseId: string) => void;
}

export const DocumentSummaryPanel: React.FC<DocumentSummaryPanelProps> = ({
  documentId,
  isReady,
  onPageNavigate,
  onClauseSelect,
}) => {
  const queryClient = useQueryClient();
  const [generateError, setGenerateError] = useState<string | null>(null);

  const {
    data: summaryResponse,
    isLoading,
  } = useQuery({
    queryKey: ["document-summary", documentId],
    queryFn: () => fetchDocumentSummary(documentId),
    enabled: !!documentId && isReady,
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: (force: boolean) => generateDocumentSummary(documentId, force),
    onSuccess: (data) => {
      setGenerateError(null);
      if (!data.success && data.error) {
        setGenerateError(data.error.message);
      }
      queryClient.invalidateQueries({ queryKey: ["document-summary", documentId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to generate summary";
      setGenerateError(msg);
    },
  });

  if (!isReady) {
    return (
      <div className="p-6 text-center text-slate-500 space-y-2 bg-slate-50 rounded-lg border border-slate-200">
        <Info className="w-6 h-6 mx-auto text-slate-400" />
        <p className="text-sm font-medium">Document is not ready for analysis</p>
        <p className="text-xs text-slate-400">
          The processing pipeline must complete before generating an AI summary.
        </p>
      </div>
    );
  }

  const summaryData = summaryResponse?.data;
  const isNotFound =
    summaryResponse?.error?.code === "ANALYSIS_NOT_FOUND" ||
    (!isLoading && !summaryData && !generateMutation.isPending);

  const isGenerating = generateMutation.isPending || summaryData?.status === "GENERATING";

  return (
    <div className="space-y-4">
      {/* AI Safety Disclaimer Notice */}
      <SafetyDisclaimer />

      {/* Generation in progress state */}
      {isGenerating && (
        <div className="p-8 text-center bg-blue-50/50 rounded-lg border border-blue-200 space-y-3">
          <Loader2 className="w-7 h-7 text-blue-600 animate-spin mx-auto" />
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-blue-900">
              Generating Plain-Language AI Summary
            </h4>
            <p className="text-xs text-blue-700 max-w-md mx-auto">
              Assembling evidence pack from clauses, entities, and text chunks, and running conservative fact-checked comprehension...
            </p>
          </div>
        </div>
      )}

      {/* Error state */}
      {(generateError || (summaryResponse && !summaryResponse.success && !isNotFound)) && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 space-y-2">
          <div className="flex items-center gap-1.5 font-bold">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>
              {summaryResponse?.error?.code === "AI_PROVIDER_UNAVAILABLE"
                ? "AI Provider Unavailable"
                : summaryResponse?.error?.code === "AI_OUTPUT_VALIDATION_FAILED"
                ? "Verification Guard Failed"
                : "Analysis Error"}
            </span>
          </div>
          <p>{generateError || summaryResponse?.error?.message}</p>
          <button
            onClick={() => generateMutation.mutate(true)}
            className="px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-900 rounded font-semibold text-xs transition"
          >
            Retry Generation
          </button>
        </div>
      )}

      {/* Not yet generated state */}
      {isNotFound && !isGenerating && (
        <div className="p-8 text-center bg-slate-50 rounded-lg border border-slate-200 space-y-3">
          <Sparkles className="w-8 h-8 text-amber-500 mx-auto" />
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-slate-800">No AI Summary Generated Yet</h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Generate a plain-language summary of this legal document. Every point is verified and linked to source clauses and pages.
            </p>
          </div>
          <button
            onClick={() => generateMutation.mutate(false)}
            disabled={generateMutation.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-xs inline-flex items-center gap-2 shadow-xs transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Generate Document Summary
          </button>
        </div>
      )}

      {/* Completed Summary View */}
      {summaryData && summaryData.status === "COMPLETED" && (
        <div className="space-y-4">
          {/* Header controls & Provenance metadata */}
          <div className="flex items-center justify-between bg-slate-50 px-3.5 py-2 rounded-lg border border-slate-200 text-[11px] text-slate-500">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>
                Verified AI Summary ·{" "}
                <span className="font-mono text-slate-700">
                  {summaryData.provider}/{summaryData.model}
                </span>{" "}
                · <span className="font-mono">{summaryData.prompt_version}</span>
              </span>
            </div>
            <button
              onClick={() => generateMutation.mutate(true)}
              disabled={generateMutation.isPending}
              className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> Regenerate
            </button>
          </div>

          {/* Purpose & Overview */}
          <div className="p-4 rounded-lg bg-white border border-slate-200 space-y-3 shadow-xs">
            {summaryData.purpose && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider">
                  Document Purpose
                </span>
                <p className="text-xs font-semibold text-slate-900 leading-relaxed">
                  {summaryData.purpose}
                </p>
              </div>
            )}

            {summaryData.summary && (
              <div className="space-y-1 pt-2 border-t border-slate-100">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  Executive Summary
                </span>
                <p className="text-xs text-slate-700 font-serif leading-relaxed whitespace-pre-wrap">
                  {summaryData.summary}
                </p>
              </div>
            )}
          </div>

          {/* Key Points with Evidence Tracing */}
          {summaryData.key_points && summaryData.key_points.length > 0 && (
            <div className="p-4 rounded-lg bg-white border border-slate-200 space-y-3 shadow-xs">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-600" />
                Key Points ({summaryData.key_points.length})
              </h4>
              <div className="space-y-2.5">
                {summaryData.key_points.map((kp: KeyPoint, idx: number) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-50/70 rounded-md border border-slate-150 space-y-2"
                  >
                    <p className="text-xs text-slate-800 font-medium leading-relaxed">
                      {kp.text}
                    </p>
                    {kp.evidence_refs && kp.evidence_refs.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[10px] font-semibold text-slate-400">
                          Evidence:
                        </span>
                        {kp.evidence_refs.map((ref: string) => (
                          <EvidenceReference
                            key={ref}
                            evidenceRef={ref}
                            onClick={() => {
                              if (ref.startsWith("clause-") && onClauseSelect) {
                                onClauseSelect(ref.replace("clause-", ""));
                              } else if (ref.startsWith("page-")) {
                                onPageNavigate(1);
                              }
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Conservative Check Signals */}
          {summaryData.check_signals && summaryData.check_signals.length > 0 && (
            <div className="p-4 rounded-lg bg-amber-50/40 border border-amber-200 space-y-3 shadow-xs">
              <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                Conservative "Check This" Observations ({summaryData.check_signals.length})
              </h4>
              <p className="text-[11px] text-amber-800 leading-normal">
                These are items in the document that warrant verification or clarity. They are not legal conclusions.
              </p>
              <div className="space-y-2">
                {summaryData.check_signals.map((sig: CheckSignal, idx: number) => {
                  const severityBadge =
                    sig.severity === "HIGH_ATTENTION"
                      ? "bg-red-100 text-red-800 border-red-200"
                      : sig.severity === "ATTENTION"
                      ? "bg-amber-100 text-amber-800 border-amber-200"
                      : "bg-blue-100 text-blue-800 border-blue-200";

                  return (
                    <div
                      key={idx}
                      className="p-3 bg-white rounded-md border border-amber-200/80 space-y-1.5 shadow-2xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-slate-800">
                          {sig.category.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${severityBadge}`}
                        >
                          {sig.severity}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed">{sig.message}</p>
                      {sig.explanation && (
                        <p className="text-[11px] text-slate-500 italic">
                          Why this matters: {sig.explanation}
                        </p>
                      )}
                      {sig.evidence_refs && sig.evidence_refs.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1 pt-1">
                          {sig.evidence_refs.map((ref) => (
                            <EvidenceReference key={ref} evidenceRef={ref} />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Two-Column Grid: Dates & Amounts | Parties & Obligations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Dates & Amounts */}
            <div className="p-4 rounded-lg bg-white border border-slate-200 space-y-3 shadow-xs">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-red-600" /> Important Dates
              </h4>
              {summaryData.important_dates.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No dates highlighted.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {summaryData.important_dates.map((d: string, i: number) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-red-500 font-bold">•</span>
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              )}

              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5 pt-2 border-t border-slate-100">
                <IndianRupee className="w-3.5 h-3.5 text-emerald-600" /> Important Amounts
              </h4>
              {summaryData.important_amounts.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No monetary amounts highlighted.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {summaryData.important_amounts.map((a: string, i: number) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-emerald-500 font-bold">•</span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Parties & Obligations */}
            <div className="p-4 rounded-lg bg-white border border-slate-200 space-y-3 shadow-xs">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-indigo-600" /> Parties Involved
              </h4>
              {summaryData.important_parties.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No parties highlighted.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {summaryData.important_parties.map((p: string, i: number) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-indigo-500 font-bold">•</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              )}

              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5 pt-2 border-t border-slate-100">
                <CheckCircle className="w-3.5 h-3.5 text-blue-600" /> Declared Obligations
              </h4>
              {summaryData.obligations.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No explicit duties noted.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {summaryData.obligations.map((o: string, i: number) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-blue-500 font-bold">•</span>
                      <span>{o}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Uncertainty Notes */}
          {summaryData.uncertainty_notes && summaryData.uncertainty_notes.length > 0 && (
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
                Disclosed Uncertainties & Limitations
              </h4>
              <ul className="space-y-1 text-xs text-slate-600">
                {summaryData.uncertainty_notes.map((u: string, i: number) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-slate-400 font-bold">•</span>
                    <span>{u}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
