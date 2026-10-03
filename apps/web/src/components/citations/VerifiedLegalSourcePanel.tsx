import React from "react";
import { BookOpen, ExternalLink, Info, ShieldCheck } from "lucide-react";
import { LegalCitation } from "../../types";

interface VerifiedLegalSourcePanelProps {
  citations?: LegalCitation[] | null;
  externalContext?: string[] | null;
}

export const VerifiedLegalSourcePanel: React.FC<VerifiedLegalSourcePanelProps> = ({
  citations,
  externalContext,
}) => {
  if ((!citations || citations.length === 0) && (!externalContext || externalContext.length === 0)) {
    return null;
  }

  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-emerald-900 font-semibold text-sm">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Verified Indian Legal Sources (Contextual Reference)</span>
        </div>
        <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-200/70 text-emerald-800">
          External Reference
        </span>
      </div>

      <div className="flex items-center gap-2 text-xs text-emerald-800 bg-emerald-100/60 p-2.5 rounded border border-emerald-200/60">
        <Info className="w-4 h-4 text-emerald-700 shrink-0" />
        <p>
          <strong>Notice:</strong> These verified legal sources provide general statutory context. They are{" "}
          <strong>NOT legal advice</strong> and do not predict court outcomes. The uploaded document is the primary
          source for what your agreement says.
        </p>
      </div>

      {externalContext && externalContext.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <p className="text-xs font-semibold text-emerald-950 uppercase tracking-wider text-[11px]">
            Contextual Legal Observations
          </p>
          <ul className="list-disc list-inside space-y-1 text-xs text-emerald-900">
            {externalContext.map((ctx, idx) => (
              <li key={idx} className="leading-relaxed">
                {ctx}
              </li>
            ))}
          </ul>
        </div>
      )}

      {citations && citations.length > 0 && (
        <div className="space-y-2 pt-2">
          <p className="text-xs font-semibold text-emerald-950 uppercase tracking-wider text-[11px]">
            Authoritative Citations
          </p>
          <div className="grid grid-cols-1 gap-2">
            {citations.map((c) => (
              <div
                key={c.citation_id}
                className="flex items-center justify-between p-2.5 bg-white border border-emerald-200 rounded-md text-xs shadow-2xs hover:border-emerald-300 transition"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 font-medium text-slate-900">
                    <BookOpen className="w-3.5 h-3.5 text-emerald-600" />
                    <span>{c.source_name}</span>
                    {c.section && (
                      <span className="font-bold text-emerald-800 bg-emerald-50 px-1 rounded border border-emerald-100">
                        {c.section}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Authority: {c.authority} · Version: {c.version}
                    {c.effective_date ? ` (Effective: ${new Date(c.effective_date).toLocaleDateString()})` : ""}
                  </p>
                </div>

                <a
                  href={c.official_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50 border border-emerald-200 rounded transition shrink-0 ml-3"
                  title="View official publication or statute on government portal"
                >
                  <span>Official Text</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
