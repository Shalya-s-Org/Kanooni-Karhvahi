import React from "react";
import { ShieldAlert } from "lucide-react";

interface SafetyDisclaimerProps {
  compact?: boolean;
}

export const SafetyDisclaimer: React.FC<SafetyDisclaimerProps> = ({ compact = false }) => {
  return (
    <div
      className={`rounded-lg border border-amber-200 bg-amber-50/80 text-amber-900 flex items-start gap-2.5 ${
        compact ? "p-2.5 text-[11px]" : "p-3.5 text-xs shadow-xs"
      }`}
    >
      <ShieldAlert className={`shrink-0 text-amber-600 mt-0.5 ${compact ? "w-3.5 h-3.5" : "w-4 h-4"}`} />
      <div className="space-y-0.5 leading-relaxed">
        <span className="font-semibold text-amber-950">Informational Notice: </span>
        <span>
          AI-generated information is based strictly on this document and is not legal advice.
          Verify important matters with the relevant official source or a qualified lawyer.
        </span>
      </div>
    </div>
  );
};
