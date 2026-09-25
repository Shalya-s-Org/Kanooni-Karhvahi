import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { FileUploadZone } from "./components/document/FileUploadZone";
import { DocumentViewer } from "./components/document/DocumentViewer";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function IntakePage() {
  const navigate = useNavigate();
  return (
    <main className="flex-1 flex items-center justify-center p-6">
      <FileUploadZone onUploadSuccess={(id) => navigate(`/document/${id}`)} />
    </main>
  );
}

function DocumentPage() {
  return <DocumentViewer />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
                  Phase 4: Semantic Retrieval
                </span>
              </div>
            </div>
          </header>

          {/* Legal Disclaimer */}
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 text-xs text-amber-900 flex items-center justify-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0" />
            <p className="text-center font-medium">
              <strong>Legal Disclaimer:</strong> Kanooni Karhvahi is an AI document companion for informational purposes only. It is <strong>not a lawyer</strong>, does not give legal advice, and does not forecast case outcomes.
            </p>
          </div>

          {/* Routes */}
          <Routes>
            <Route path="/" element={<IntakePage />} />
            <Route path="/document/:id" element={<DocumentPage />} />
          </Routes>

          {/* Footer */}
          <footer className="bg-white border-t border-slate-200 px-6 py-4 text-center text-xs text-slate-500">
            <p>Kanooni Karhvahi &copy; {new Date().getFullYear()} — Built for transparency and document grounding.</p>
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
