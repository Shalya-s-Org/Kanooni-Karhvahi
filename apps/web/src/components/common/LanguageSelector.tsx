import React from "react";
import { Languages } from "lucide-react";
import { SupportedLanguageItem } from "../../types";

interface LanguageSelectorProps {
  languages: SupportedLanguageItem[];
  selectedLanguage: string | null;
  onSelect: (code: string) => void;
  isLoading?: boolean;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  languages,
  selectedLanguage,
  onSelect,
  isLoading = false,
}) => {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 shrink-0">
        <Languages className="w-3.5 h-3.5 text-violet-600" />
        <span>Translate:</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {languages.map((lang) => (
          <button
            key={lang.code}
            onClick={() => onSelect(selectedLanguage === lang.code ? "" : lang.code)}
            disabled={isLoading}
            className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all ${
              selectedLanguage === lang.code
                ? "bg-violet-600 text-white border-violet-600 shadow-sm"
                : "bg-white text-slate-700 border-slate-200 hover:border-violet-400 hover:text-violet-700"
            } disabled:opacity-50`}
          >
            {lang.name}
          </button>
        ))}
      </div>
    </div>
  );
};
