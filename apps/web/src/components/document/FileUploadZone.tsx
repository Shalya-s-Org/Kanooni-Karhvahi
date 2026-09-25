import React, { useState, useRef } from "react";
import { UploadCloud, AlertCircle, Loader2, Type, CheckCircle } from "lucide-react";
import { uploadDocument, intakePastedText } from "../../services/api";

interface FileUploadZoneProps {
  onUploadSuccess: (documentId: string) => void;
}

export const FileUploadZone: React.FC<FileUploadZoneProps> = ({ onUploadSuccess }) => {
  const [activeTab, setActiveTab] = useState<"file" | "text">("file");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pasted text form state
  const [pastedText, setPastedText] = useState("");
  const [pastedFilename, setPastedFilename] = useState("legal-notice.txt");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await handleFileSelection(e.target.files[0]);
    }
  };

  const handleFileSelection = async (file: File) => {
    setError(null);

    // Client-side quick validation
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
      setError("File exceeds the 25 MB maximum limit.");
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase();
    const validExts = ["pdf", "jpg", "jpeg", "png", "tif", "tiff"];
    if (!ext || !validExts.includes(ext)) {
      setError(`Unsupported file extension '.${ext}'. Supported formats: PDF, JPEG, PNG, TIFF.`);
      return;
    }

    setIsUploading(true);
    const res = await uploadDocument(file);
    setIsUploading(false);

    if (res.success && res.data) {
      onUploadSuccess(res.data.document_id);
    } else {
      setError(res.error?.message || "Failed to upload document. Please check the file and try again.");
    }
  };

  const handlePastedTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!pastedText.trim()) {
      setError("Please paste the legal text or clause.");
      return;
    }

    setIsUploading(true);
    const res = await intakePastedText(pastedText, pastedFilename);
    setIsUploading(false);

    if (res.success && res.data) {
      onUploadSuccess(res.data.document_id);
    } else {
      setError(res.error?.message || "Failed to submit legal text.");
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Tab selection */}
      <div className="flex border-b border-slate-200 bg-slate-50/50">
        <button
          type="button"
          onClick={() => { setActiveTab("file"); setError(null); }}
          className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
            activeTab === "file"
              ? "border-amber-600 text-amber-700 bg-white"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          Upload Document (PDF / Images)
        </button>
        <button
          type="button"
          onClick={() => { setActiveTab("text"); setError(null); }}
          className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
            activeTab === "text"
              ? "border-amber-600 text-amber-700 bg-white"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Type className="w-4 h-4" />
          Paste Legal Text
        </button>
      </div>

      <div className="p-6">
        {/* Error notification banner */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {activeTab === "file" ? (
          <div>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragging
                  ? "border-amber-500 bg-amber-50/50 scale-[0.99]"
                  : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,application/pdf,image/*"
                onChange={handleFileChange}
                disabled={isUploading}
              />

              <div className="flex flex-col items-center justify-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center text-amber-600">
                  {isUploading ? (
                    <Loader2 className="w-6 h-6 animate-spin" />
                  ) : (
                    <UploadCloud className="w-6 h-6" />
                  )}
                </div>

                <div>
                  <p className="text-sm font-semibold text-slate-800">
                    {isUploading ? "Uploading document to vault..." : "Click to browse or drag & drop file"}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Accepts Indian legal notices, agreements, court petitions, and orders.
                  </p>
                </div>

                {/* Formats badges */}
                <div className="flex items-center gap-1.5 flex-wrap justify-center pt-2">
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[11px] font-medium border border-slate-200">PDF</span>
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[11px] font-medium border border-slate-200">JPEG</span>
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[11px] font-medium border border-slate-200">PNG</span>
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[11px] font-medium border border-slate-200">TIFF</span>
                  <span className="text-[11px] text-slate-400 ml-1">· Max 25 MB</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 text-center mt-3">
              🔒 <strong>24-Hour Ephemeral Privacy:</strong> Documents are automatically purged from storage within 24 hours.
            </p>
          </div>
        ) : (
          <form onSubmit={handlePastedTextSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Document Label / Reference
              </label>
              <input
                type="text"
                value={pastedFilename}
                onChange={(e) => setPastedFilename(e.target.value)}
                placeholder="e.g. Legal_Notice_Dated_2026.txt"
                className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Legal Text Content
              </label>
              <textarea
                rows={7}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                placeholder="Paste contract clauses, dispute notices, or petition text here..."
                className="w-full text-xs p-3 border border-slate-200 rounded-lg font-mono focus:outline-none focus:ring-1 focus:ring-amber-500"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isUploading || !pastedText.trim()}
              className="w-full py-2.5 px-4 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Submitting Text...
                </>
              ) : (
                <>
                  <CheckCircle className="w-3.5 h-3.5" />
                  Intake Text Document
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
