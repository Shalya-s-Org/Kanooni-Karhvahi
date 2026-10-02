import React from "react";
import { Bookmark, ExternalLink } from "lucide-react";

interface EvidenceReferenceProps {
  evidenceRef: string;
  sourceType?: string;
  pageNumber?: number;
  clauseNumber?: string | null;
  snippet?: string;
  onClick?: () => void;
}

export const EvidenceReference: React.FC<EvidenceReferenceProps> = ({
  evidenceRef,
  sourceType,
  pageNumber,
  clauseNumber,
  snippet,
  onClick,
}) => {
  // Infer human-readable label from evidence ID prefix if not explicitly provided
  const inferredType = (() => {
    if (sourceType) return sourceType;
    if (evidenceRef.startsWith("clause-")) return "Direct clause evidence";
    if (evidenceRef.startsWith("entity-")) return "Extracted entity evidence";
    if (evidenceRef.startsWith("chunk-")) return "Semantic chunk evidence";
    if (evidenceRef.startsWith("page-")) return "Page text evidence";
    if (evidenceRef.startsWith("cls-")) return "Classification evidence";
    return "Document evidence";
  })();

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 text-[11px] text-slate-700 hover:text-blue-800 transition cursor-pointer font-medium text-left group"
      title={snippet ? `Source: "${snippet}"` : `Evidence ID: ${evidenceRef}`}
    >
      <Bookmark className="w-3 h-3 text-slate-400 group-hover:text-blue-600 shrink-0" />
      <span className="font-mono text-[10px] text-slate-500 group-hover:text-blue-700">
        {pageNumber != null ? `P.${pageNumber}` : ""}
        {clauseNumber ? ` · Cl.${clauseNumber}` : ""}
        {pageNumber == null && !clauseNumber ? evidenceRef : ""}
      </span>
      <span className="text-[10px] text-slate-400 font-normal">({inferredType})</span>
      <ExternalLink className="w-2.5 h-2.5 text-slate-400 group-hover:text-blue-500 opacity-60 group-hover:opacity-100 shrink-0 ml-0.5" />
    </button>
  );
};
