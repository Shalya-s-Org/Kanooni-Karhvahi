import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchClauseExplanation,
  generateClauseExplanation,
} from "../../services/api";
import { DocumentClauseItem, CheckSignal, ImportantTerm } from "../../types";
import { EvidenceReference } from "./EvidenceReference";
import { SafetyDisclaimer } from "./SafetyDisclaimer";
import {
  Sparkles,
  Loader2,
  AlertTriangle,
  HelpCircle,
  ShieldCheck,
  RefreshCw,
  BookOpen,
} from "lucide-react";

interface ClauseExplanationCardProps {
  documentId: string;
  clause: DocumentClauseItem;
  isSelected: boolean;
  onSelect: () => void;
}

export const ClauseExplanationCard: React.FC<ClauseExplanationCardProps> = ({
  documentId,
  clause,
  isSelected,
  onSelect,
}) => {
  const queryClient = useQueryClient();
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Lazy query: enabled once user expands or requests explanation
  const { data: explanationResponse } = useQuery({
    queryKey: ["clause-explanation", documentId, clause.id],
    queryFn: () => fetchClauseExplanation(documentId, clause.id),
    enabled: !!documentId && !!clause.id && isExpanded,
    retry: false,
  });

  const explainMutation = useMutation({
    mutationFn: (force: boolean) =>
      generateClauseExplanation(documentId, clause.id, force),
    onSuccess: (data) => {
      setActionError(null);
      if (!data.success && data.error) {
        setActionError(data.error.message);
      }
      queryClient.invalidateQueries({
        queryKey: ["clause-explanation", documentId, clause.id],
      });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to explain clause";
      setActionError(msg);
    },
  });

  const explanation = explanationResponse?.data;
  const isGenerating = explainMutation.isPending || explanation?.status === "GENERATING";
  const hasExplanation = explanation && explanation.status === "COMPLETED";

  const handleExplainClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(true);
    if (!hasExplanation && !isGenerating) {
      explainMutation.mutate(false);
    }
  };

  return (
    <div
      onClick={onSelect}
      className={`rounded-lg border transition cursor-pointer overflow-hidden ${
        isSelected
          ? "border-blue-500 bg-blue-50/30 shadow-xs"
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      {/* Clause Header & Original Text Section */}
      <div className="p-3.5 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {clause.clause_number && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-800 rounded font-bold text-xs font-mono">
                {clause.clause_number}
              </span>
            )}
            {clause.title && (
              <h4 className="text-xs font-bold text-slate-800">{clause.title}</h4>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-medium">
              Page {clause.page_start}
              {clause.page_end > clause.page_start ? `–${clause.page_end}` : ""}
            </span>
            <button
              type="button"
              onClick={handleExplainClick}
              disabled={isGenerating}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center gap-1 transition ${
                hasExplanation
                  ? "bg-blue-100 hover:bg-blue-200 text-blue-800"
                  : "bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
              }`}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" /> Explaining...
                </>
              ) : hasExplanation ? (
                <>
                  <BookOpen className="w-3 h-3" />
                  {isExpanded ? "Hide Explanation" : "View Explanation"}
                </>
              ) : (
                <>
                  <Sparkles className="w-3 h-3" /> Explain Clause
                </>
              )}
            </button>
          </div>
        </div>

        {/* ALWAYS PRESENT: Original Clause Text */}
        <div className="space-y-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Original Clause Text
          </span>
          <p className="text-xs text-slate-800 whitespace-pre-wrap font-serif leading-relaxed line-clamp-4">
            {clause.original_text}
          </p>
        </div>
      </div>

      {/* AI-Generated Explanation Section */}
      {isExpanded && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="p-3.5 bg-slate-50 border-t border-slate-200 space-y-3"
        >
          {/* Safety Disclaimer Banner */}
          <SafetyDisclaimer compact />

          {/* Loading state */}
          {isGenerating && (
            <div className="p-4 text-center text-blue-700 bg-white rounded border border-blue-200 flex items-center justify-center gap-2 text-xs">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              <span>Analyzing clause with bounded legal evidence...</span>
            </div>
          )}

          {/* Action error */}
          {actionError && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-start gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{actionError}</span>
            </div>
          )}

          {/* Completed Explanation */}
          {hasExplanation && explanation && (
            <div className="space-y-3">
              {/* Provenance metadata header */}
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span className="font-semibold text-slate-700 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  AI-Generated Explanation ({explanation.provider}/{explanation.model})
                </span>
                <button
                  type="button"
                  onClick={() => explainMutation.mutate(true)}
                  disabled={explainMutation.isPending}
                  className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-1 cursor-pointer"
                >
                  <RefreshCw className="w-2.5 h-2.5" /> Regenerate
                </button>
              </div>

              {/* Plain Meaning */}
              {explanation.plain_meaning && (
                <div className="p-3 bg-white rounded border border-slate-200 space-y-1">
                  <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider">
                    Plain Meaning
                  </span>
                  <p className="text-xs text-slate-800 leading-relaxed font-serif">
                    {explanation.plain_meaning}
                  </p>
                </div>
              )}

              {/* Why It Matters */}
              {explanation.why_it_matters && (
                <div className="p-3 bg-white rounded border border-slate-200 space-y-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Why This Matters
                  </span>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {explanation.why_it_matters}
                  </p>
                </div>
              )}

              {/* Important Terms */}
              {explanation.important_terms && explanation.important_terms.length > 0 && (
                <div className="p-3 bg-white rounded border border-slate-200 space-y-2">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Important Terms Explained
                  </span>
                  <div className="space-y-1.5">
                    {explanation.important_terms.map((t: ImportantTerm, i: number) => (
                      <div key={i} className="text-xs">
                        <span className="font-semibold text-slate-800 font-mono text-[11px]">
                          {t.term}
                        </span>
                        : <span className="text-slate-600">{t.explanation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Check Signals for this Clause */}
              {explanation.check_signals && explanation.check_signals.length > 0 && (
                <div className="p-3 bg-amber-50/60 rounded border border-amber-200 space-y-2">
                  <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3 text-amber-600" />
                    Conservative Observations
                  </span>
                  <div className="space-y-1.5">
                    {explanation.check_signals.map((sig: CheckSignal, i: number) => (
                      <div key={i} className="text-xs text-slate-700 space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-800">{sig.category}</span>
                          <span className="px-1 py-0.2 bg-amber-100 text-amber-800 text-[9px] rounded font-bold">
                            {sig.severity}
                          </span>
                        </div>
                        <p>{sig.message}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Evidence references */}
              {explanation.evidence_refs && explanation.evidence_refs.length > 0 && (
                <div className="flex flex-wrap items-center gap-1 pt-1">
                  <span className="text-[10px] text-slate-400 font-semibold">Evidence:</span>
                  {explanation.evidence_refs.map((ref: string) => (
                    <EvidenceReference key={ref} evidenceRef={ref} />
                  ))}
                </div>
              )}

              {/* Uncertainty notes */}
              {explanation.uncertainty_notes && explanation.uncertainty_notes.length > 0 && (
                <div className="p-2 bg-slate-100 rounded text-[11px] text-slate-500 space-y-0.5">
                  <span className="font-semibold flex items-center gap-1">
                    <HelpCircle className="w-3 h-3" /> Limitations & Uncertainties:
                  </span>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {explanation.uncertainty_notes.map((u: string, i: number) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
