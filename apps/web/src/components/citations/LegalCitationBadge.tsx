import React from "react";
import { BookOpen, ExternalLink, ShieldCheck } from "lucide-react";
import { LegalCitation } from "../../types";

interface LegalCitationBadgeProps {
  citation: LegalCitation;
  className?: string;
}

export const LegalCitationBadge: React.FC<LegalCitationBadgeProps> = ({
  citation,
  className = "",
}) => {
  return (
    <div
      className={`inline-flex items-center flex-wrap gap-2 px-3 py-1.5 rounded-md bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 transition hover:bg-emerald-100/80 shadow-xs ${className}`}
      title={`Authority: ${citation.authority} | Version: ${citation.version} | Retrieved: ${citation.retrieved_at}`}
    >
      <div className="flex items-center gap-1.5 font-semibold text-emerald-800 shrink-0">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        <span className="uppercase tracking-wider text-[10px] bg-emerald-200/60 text-emerald-800 px-1.5 py-0.5 rounded font-mono">
          Verified Legal Source
        </span>
      </div>

      <span className="font-medium text-emerald-950 flex items-center gap-1">
        <BookOpen className="w-3 h-3 text-emerald-700 inline" />
        {citation.source_name}
        {citation.section && (
          <span className="font-bold text-emerald-800">
            · {citation.section}
            {citation.subsection ? ` ${citation.subsection}` : ""}
          </span>
        )}
      </span>

      {citation.effective_date && (
        <span className="text-[10px] text-emerald-700 bg-white/70 px-1.5 py-0.5 rounded border border-emerald-200/60">
          Eff: {new Date(citation.effective_date).toLocaleDateString()}
        </span>
      )}

      {citation.official_url && (
        <a
          href={citation.official_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 text-emerald-700 hover:text-emerald-950 underline underline-offset-2 ml-auto text-[11px] font-medium"
        >
          <span>Official Link</span>
          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
        </a>
      )}
    </div>
  );
};
