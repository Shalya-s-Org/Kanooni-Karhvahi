import React from "react";
import { Loader2, AlertTriangle, Languages, RotateCcw, ShieldCheck, BookOpen } from "lucide-react";
import { TranslationData } from "../../types";

interface TranslatedTextPanelProps {
  translationData: TranslationData | null;
  isLoading: boolean;
  error: string | null;
  targetLanguageName: string;
  onRetry?: () => void;
  compact?: boolean;
}

export const TranslatedTextPanel: React.FC<TranslatedTextPanelProps> = ({
  translationData,
  isLoading,
  error,
  targetLanguageName,
  onRetry,
  compact = false,
}) => {
  if (isLoading) {
    return (
      <div className={`flex items-center gap-2 ${compact ? "py-2" : "py-6"} justify-center text-violet-700 bg-violet-50/50 rounded-lg border border-violet-200`}>
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-xs font-medium">Translating to {targetLanguageName}...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
        <div className="space-y-1">
          <span className="font-semibold">Translation failed:</span>
          <p>{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 mt-1.5 px-2.5 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded font-semibold transition"
            >
              <RotateCcw className="w-3 h-3" /> Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!translationData) return null;

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50/40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-violet-600/5 border-b border-violet-200">
        <div className="flex items-center gap-2">
          <Languages className="w-3.5 h-3.5 text-violet-600" />
          <span className="text-xs font-bold text-violet-900">
            {translationData.target_language_name} Translation
          </span>
          <span className="px-1.5 py-0.5 text-[10px] bg-violet-100 text-violet-700 rounded font-mono border border-violet-200">
            {translationData.target_language.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-violet-600">
          <ShieldCheck className="w-3 h-3" />
          <span>{translationData.provider}/{translationData.model}</span>
        </div>
      </div>

      {/* Translated content */}
      <div className="p-3.5 space-y-2">
        <p className={`text-slate-800 whitespace-pre-wrap leading-relaxed font-serif ${compact ? "text-xs" : "text-sm"}`}>
          {translationData.translated_text}
        </p>

        {/* Legal terms preservation notice */}
        {translationData.preserved_terms.length > 0 && (
          <div className="flex items-start gap-2 pt-2 border-t border-violet-100 text-[11px] text-violet-700">
            <BookOpen className="w-3 h-3 shrink-0 mt-0.5" />
            <span>
              <strong>Preserved in English:</strong>{" "}
              {translationData.preserved_terms.slice(0, 8).join(", ")}
              {translationData.preserved_terms.length > 8 ? ` +${translationData.preserved_terms.length - 8} more` : ""}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
