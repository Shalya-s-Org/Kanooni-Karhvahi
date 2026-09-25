import { useEffect, useState } from "react";
import { fetchHealth } from "./services/api";
import { HealthData, ApiResponse } from "./types";
import { ShieldAlert, FileText, CheckCircle2, Server, Database, Activity, RefreshCw } from "lucide-react";

export function App() {
  const [health, setHealth] = useState<ApiResponse<HealthData> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const checkStatus = async () => {
    setLoading(true);
    const data = await fetchHealth();
    setHealth(data);
    setLoading(false);
  };

  useEffect(() => {
    checkStatus();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-slate-900 text-white border-b border-slate-800 px-6 py-4 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-amber-500 text-slate-950 p-2 rounded-lg font-bold text-lg">
              क
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Kanooni Karhvahi</h1>
              <p className="text-xs text-slate-400">A Multilingual Legal-Document Companion for India</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs">
            <span className="px-2.5 py-1 bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-full font-medium">
              Phase 1: Foundation
            </span>
          </div>
        </div>
      </header>

      {/* Legal Disclaimer Bar */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 text-xs text-amber-900 flex items-center justify-center space-x-2">
        <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0" />
        <p className="text-center font-medium">
          <strong>Legal Disclaimer:</strong> Kanooni Karhvahi is an AI document companion for informational purposes only. It is <strong>not a lawyer</strong>, does not give legal advice, and does not forecast case outcomes.
        </p>
      </div>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto w-full p-6 space-y-6">
        {/* Status Card */}
        <section className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Activity className="w-5 h-5 text-indigo-600" />
                System Health & Connectivity Probe
              </h2>
              <p className="text-sm text-slate-500">Live heartbeat to backend API, PostgreSQL, and Redis.</p>
            </div>
            <button
              onClick={checkStatus}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh Status
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* API Status */}
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-3">
              <Server className="w-5 h-5 text-slate-600 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500 font-medium">FastAPI Backend</p>
                <p className="text-sm font-semibold text-slate-800">
                  {health?.success ? "Online (HTTP 200)" : "Connecting / Offline"}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {health?.data ? `${health.data.service} v${health.data.version}` : "Waiting for API response"}
                </p>
              </div>
            </div>

            {/* DB Status */}
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-3">
              <Database className="w-5 h-5 text-slate-600 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500 font-medium">PostgreSQL (pgvector)</p>
                <p className="text-sm font-semibold text-slate-800">
                  {health?.data?.database?.connected ? (
                    <span className="text-emerald-600 flex items-center gap-1">Connected</span>
                  ) : (
                    <span className="text-amber-600">Pending Stack Boot</span>
                  )}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {health?.data?.database?.message || "PostgreSQL 16"}
                </p>
              </div>
            </div>

            {/* Celery / Redis */}
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-3">
              <Activity className="w-5 h-5 text-slate-600 mt-0.5" />
              <div>
                <p className="text-xs text-slate-500 font-medium">Redis & Celery</p>
                <p className="text-sm font-semibold text-slate-800">
                  {health?.data?.redis?.connected ? (
                    <span className="text-emerald-600 flex items-center gap-1">Connected</span>
                  ) : (
                    <span className="text-amber-600">Pending Stack Boot</span>
                  )}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {health?.data?.redis?.message || "Redis 7 Queue"}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Phase 1 Architecture Blueprint Shell (Preview of side-by-side workspace) */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm flex flex-col items-center justify-center text-center min-h-[280px]">
            <FileText className="w-12 h-12 text-slate-300 mb-3" />
            <h3 className="text-base font-semibold text-slate-900">Original Document Workspace</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              In Phase 2, this pane will house the high-fidelity PDF/image viewer with interactive clause bounding boxes.
            </p>
            <span className="mt-4 px-3 py-1 bg-slate-100 text-slate-600 text-xs rounded-full border border-slate-200">
              Workspace Slot: Left Pane
            </span>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between min-h-[280px]">
            <div>
              <h3 className="text-base font-semibold text-slate-900 mb-2">Phase 1 Foundations Completed</h3>
              <ul className="space-y-2 text-xs text-slate-600">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Monorepo layout: <code>apps/web</code>, <code>services/api</code>, <code>services/worker</code></span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>FastAPI layered architecture with standard JSON response envelopes</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Celery worker app configured with task stubs</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Abstract LLM, Embedding, OCR, and Storage provider interfaces</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Docker Compose orchestration with pgvector & Redis service definitions</span>
                </li>
              </ul>
            </div>
            <p className="text-xs text-slate-400 border-t border-slate-100 pt-3 mt-4">
              All AI, OCR, RAG, and translation modules remain bounded for Phase 2+.
            </p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 px-6 py-4 text-center text-xs text-slate-500">
        <p>Kanooni Karhvahi &copy; {new Date().getFullYear()} — Built for transparency and document grounding.</p>
      </footer>
    </div>
  );
}

export default App;
