import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchDocumentStatus,
  fetchDocumentMetadata,
  fetchDocumentPages,
  fetchDocumentClassification,
  fetchDocumentEntities,
  fetchDocumentClauses,
  getDocumentFileUrl,
  deleteDocument,
  retryDocument,
} from "../../services/api";
import { DocumentEntityItem, DocumentClauseItem } from "../../types";
import { SemanticRetrievalPanel } from "./SemanticRetrievalPanel";
import { DocumentSummaryPanel, ClauseExplanationCard } from "../analysis";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Trash2,
  RotateCcw,
  ArrowLeft,
  FileText,
  Eye,
  Mail,
  Clock,
  IndianRupee,
  Users,
  Building2,
  Hash,
  Scale,
  ListOrdered,
  ChevronDown,
  ChevronUp,
  Tag,
  HelpCircle,
  Layers,
  Search,
  Sparkles,
} from "lucide-react";

const TERMINAL_STATUSES = new Set(["READY", "READY_WITHOUT_EMBEDDINGS", "FAILED", "DELETED"]);

export const DocumentViewer: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<"summary" | "entities" | "clauses" | "raw" | "retrieval">("summary");
  const [selectedEntity, setSelectedEntity] = useState<DocumentEntityItem | null>(null);
  const [selectedClause, setSelectedClause] = useState<DocumentClauseItem | null>(null);
  const [activePage, setActivePage] = useState<number>(1);
  const [showEvidence, setShowEvidence] = useState<boolean>(false);

  // Poll status until terminal
  const statusQuery = useQuery({
    queryKey: ["doc-status", id],
    queryFn: () => fetchDocumentStatus(id!),
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 2000;
    },
    enabled: !!id,
  });

  // Metadata
  const metaQuery = useQuery({
    queryKey: ["doc-meta", id],
    queryFn: () => fetchDocumentMetadata(id!),
    enabled: !!id,
  });

  const isReady = statusQuery.data?.data?.status === "READY" || statusQuery.data?.data?.status === "READY_WITHOUT_EMBEDDINGS";

  // Pages
  const pagesQuery = useQuery({
    queryKey: ["doc-pages", id],
    queryFn: () => fetchDocumentPages(id!),
    enabled: !!id && isReady,
  });

  // Phase 3: Classification
  const classificationQuery = useQuery({
    queryKey: ["doc-classification", id],
    queryFn: () => fetchDocumentClassification(id!),
    enabled: !!id && isReady,
  });

  // Phase 3: Entities
  const entitiesQuery = useQuery({
    queryKey: ["doc-entities", id],
    queryFn: () => fetchDocumentEntities(id!),
    enabled: !!id && isReady,
  });

  // Phase 3: Clauses
  const clausesQuery = useQuery({
    queryKey: ["doc-clauses", id],
    queryFn: () => fetchDocumentClauses(id!),
    enabled: !!id && isReady,
  });

  const status = statusQuery.data?.data;
  const meta = metaQuery.data?.data;
  const pages = pagesQuery.data?.data?.pages ?? [];
  const classification = classificationQuery.data?.data;
  const entities = entitiesQuery.data?.data?.entities ?? [];
  const clauses = clausesQuery.data?.data?.clauses ?? [];

  const handleDelete = async () => {
    if (!id) return;
    await deleteDocument(id);
    navigate("/");
  };

  const handleRetry = async () => {
    if (!id) return;
    await retryDocument(id);
    statusQuery.refetch();
  };

  const handleSelectEntity = (ent: DocumentEntityItem) => {
    setSelectedEntity(ent);
    setSelectedClause(null);
    setActivePage(ent.page_number);
  };

  const handleSelectClause = (clause: DocumentClauseItem) => {
    setSelectedClause(clause);
    setSelectedEntity(null);
    setActivePage(clause.page_start);
  };

  const isPdf = meta?.mime_type === "application/pdf";
  const isImage = meta?.mime_type?.startsWith("image/");

  // Group entities by semantic category
  const deadlines = entities.filter((e) => e.entity_type === "DEADLINE");
  const dates = entities.filter((e) => e.entity_type === "DATE");
  const amounts = entities.filter((e) => e.entity_type === "AMOUNT");
  const parties = entities.filter((e) => e.entity_type === "PERSON" || e.entity_type === "ORGANIZATION");
  const authorities = entities.filter((e) => e.entity_type === "AUTHORITY");
  const references = entities.filter((e) => e.entity_type === "REFERENCE_NUMBER" || e.entity_type === "CASE_NUMBER");
  const legalSections = entities.filter((e) => e.entity_type === "LEGAL_SECTION");
  const contacts = entities.filter((e) => e.entity_type === "EMAIL" || e.entity_type === "PHONE_NUMBER");

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-slate-100">
      {/* Top Navigation Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1 font-medium"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>
          <span className="text-xs text-slate-300">|</span>
          <span className="text-sm font-semibold text-slate-800 truncate max-w-[320px]">
            {meta?.filename || "Document"}
          </span>
          {meta?.page_count ? (
            <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full font-medium">
              {meta.page_count} page{meta.page_count > 1 ? "s" : ""}
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {status?.status === "FAILED" && status.retryable && (
            <button
              onClick={handleRetry}
              className="text-xs px-3 py-1.5 bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 flex items-center gap-1 font-medium transition"
            >
              <RotateCcw className="w-3 h-3" /> Retry
            </button>
          )}
          <button
            onClick={handleDelete}
            className="text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 flex items-center gap-1 font-medium transition"
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      </div>

      {/* Main Workspace Split View */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-0 min-h-0 overflow-hidden">
        {/* Left Pane: Original Document Viewer */}
        <div className="border-r border-slate-200 flex flex-col min-h-0 bg-slate-900/5">
          <div className="px-4 py-2.5 border-b border-slate-200 bg-white flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-blue-600" /> Original Document Source
            </h3>
            {isPdf && (
              <span className="text-xs text-slate-500 font-medium">
                Active Page: <span className="font-bold text-slate-800">{activePage}</span> / {meta?.page_count || 1}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-auto p-4 flex items-center justify-center relative">
            {!meta ? (
              <div className="text-xs text-slate-400 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading document...
              </div>
            ) : isPdf ? (
              <iframe
                key={`pdf-page-${activePage}`}
                src={`${getDocumentFileUrl(id!)}#page=${activePage}`}
                className="w-full h-full min-h-[500px] rounded-lg shadow-sm border border-slate-200 bg-white"
                title="Original PDF"
              />
            ) : isImage ? (
              <img
                src={getDocumentFileUrl(id!)}
                alt={meta.filename}
                className="max-w-full max-h-full object-contain rounded-lg shadow-sm border border-slate-200 bg-white"
              />
            ) : (
              <div className="text-center text-slate-400 p-8">
                <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p className="text-sm font-medium text-slate-600">Pasted Legal Text Document</p>
                <p className="text-xs text-slate-400 mt-1">Review structured intelligence and extracted text on the right.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Intelligence & Structured Information */}
        <div className="flex flex-col min-h-0 bg-white">
          {/* Processing Banner */}
          {status && status.status !== "READY" && (
            <div className="p-4 border-b border-slate-200 bg-slate-50 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Processing Pipeline</span>
                <StatusBadge status={status.status} />
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div
                  className="bg-amber-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${status.progress}%` }}
                />
              </div>
              <p className="text-xs text-slate-600 font-medium">{status.stage}</p>
              {status.error && (
                <div className="p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-start gap-1.5">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  {status.error}
                </div>
              )}
            </div>
          )}

          {/* Phase 3 Document Classification Header */}
          {isReady && classification && (
            <div className="p-4 border-b border-slate-200 bg-gradient-to-r from-blue-50/70 via-indigo-50/40 to-white">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[10px] font-bold text-blue-700 uppercase tracking-wider flex items-center gap-1">
                    <Tag className="w-3 h-3" /> Document Classification
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 mt-0.5">
                    {formatDocType(classification.document_type)}
                  </h2>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <ConfidenceBadge confidence={classification.confidence} />
                  {classification.evidence?.length > 0 && (
                    <button
                      onClick={() => setShowEvidence(!showEvidence)}
                      className="text-[11px] text-blue-600 hover:text-blue-800 font-medium flex items-center gap-0.5"
                    >
                      {showEvidence ? "Hide evidence" : `Evidence (${classification.evidence.length})`}
                      {showEvidence ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  )}
                </div>
              </div>

              {/* Traceable Classification Evidence */}
              {showEvidence && classification.evidence?.length > 0 && (
                <div className="mt-3 p-3 bg-white rounded-lg border border-blue-100 shadow-xs space-y-2">
                  <div className="text-[11px] font-semibold text-slate-600">Traceable Category Indicators:</div>
                  <ul className="space-y-1.5">
                    {classification.evidence.map((ev, i) => (
                      <li
                        key={i}
                        onClick={() => setActivePage(ev.page)}
                        className="text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-200 cursor-pointer hover:bg-blue-50/50 hover:border-blue-200 transition"
                      >
                        <span className="font-semibold text-blue-700 mr-1.5">Page {ev.page}:</span>
                        <span className="italic font-serif">"{ev.text}"</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Traceable Source Highlight Bar (Active Selection) */}
          {(selectedEntity || selectedClause) && (
            <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-200 flex items-start justify-between gap-3 text-xs text-amber-950">
              <div className="space-y-0.5">
                <div className="font-bold flex items-center gap-1 text-amber-800">
                  <span>Selected Source</span>
                  <span className="px-1.5 py-0.2 bg-amber-200 text-amber-900 rounded font-semibold text-[10px]">
                    Page {selectedEntity ? selectedEntity.page_number : `${selectedClause?.page_start}-${selectedClause?.page_end}`}
                  </span>
                </div>
                <p className="italic font-serif line-clamp-2">
                  "{selectedEntity ? selectedEntity.source_text : selectedClause?.original_text}"
                </p>
              </div>
              <button
                onClick={() => {
                  setSelectedEntity(null);
                  setSelectedClause(null);
                }}
                className="text-[11px] text-amber-700 hover:text-amber-900 font-semibold shrink-0"
              >
                Clear
              </button>
            </div>
          )}

          {/* Navigation Tabs */}
          {isReady && (
            <div className="flex border-b border-slate-200 px-4 bg-slate-50/50">
              <button
                onClick={() => setActiveTab("summary")}
                className={`px-4 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition ${
                  activeTab === "summary"
                    ? "border-blue-600 text-blue-600 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-500" /> AI Summary
              </button>
              <button
                onClick={() => setActiveTab("entities")}
                className={`px-4 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition ${
                  activeTab === "entities"
                    ? "border-blue-600 text-blue-600 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <Layers className="w-3.5 h-3.5" /> Key Details ({entities.length})
              </button>
              <button
                onClick={() => setActiveTab("clauses")}
                className={`px-4 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition ${
                  activeTab === "clauses"
                    ? "border-blue-600 text-blue-600 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <ListOrdered className="w-3.5 h-3.5" /> Clauses & Sections ({clauses.length})
              </button>
              <button
                onClick={() => setActiveTab("raw")}
                className={`px-4 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition ${
                  activeTab === "raw"
                    ? "border-blue-600 text-blue-600 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <FileText className="w-3.5 h-3.5" /> Extracted Text ({pages.length})
              </button>
              <button
                onClick={() => setActiveTab("retrieval")}
                className={`px-4 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition ${
                  activeTab === "retrieval"
                    ? "border-violet-600 text-violet-600 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <Search className="w-3.5 h-3.5" /> Retrieval
                <span className="ml-0.5 px-1.5 py-0.5 bg-violet-100 text-violet-700 text-[10px] font-bold rounded-full">DEV</span>
              </button>
            </div>
          )}

          {/* Tab Contents */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {/* TAB 0: AI Document Summary — Phase 5 */}
            {isReady && activeTab === "summary" && id && (
              <DocumentSummaryPanel
                documentId={id}
                isReady={isReady}
                onPageNavigate={(page) => setActivePage(page)}
                onClauseSelect={(clauseId) => {
                  const targetClause = clauses.find((c) => c.id === clauseId);
                  if (targetClause) handleSelectClause(targetClause);
                }}
              />
            )}

            {/* TAB 1: Key Details (Structured Entities) */}
            {isReady && activeTab === "entities" && (
              <div className="space-y-4">
                {/* Deadlines & Dates */}
                <EntityGroupCard
                  title="Deadlines & Action Dates"
                  icon={<Clock className="w-4 h-4 text-red-600" />}
                  count={deadlines.length + dates.length}
                >
                  {deadlines.length === 0 && dates.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No dates or deadlines detected.</p>
                  ) : (
                    <div className="space-y-2">
                      {deadlines.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-red-100 text-red-800"
                          badgeText="DEADLINE"
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                      {dates.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-slate-100 text-slate-700"
                          badgeText={(e.entity_metadata?.date_type as string) || "DATE"}
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Amounts */}
                <EntityGroupCard
                  title="Monetary Amounts"
                  icon={<IndianRupee className="w-4 h-4 text-emerald-600" />}
                  count={amounts.length}
                >
                  {amounts.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No monetary figures detected.</p>
                  ) : (
                    <div className="space-y-2">
                      {amounts.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-emerald-100 text-emerald-800"
                          badgeText={(e.entity_metadata?.amount_type as string) || "AMOUNT"}
                          extraText={e.normalized_value ? `₹${Number(e.normalized_value).toLocaleString("en-IN")}` : undefined}
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Parties & Roles */}
                <EntityGroupCard
                  title="Parties & Declared Roles"
                  icon={<Users className="w-4 h-4 text-indigo-600" />}
                  count={parties.length}
                >
                  {parties.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No named legal parties identified.</p>
                  ) : (
                    <div className="space-y-2">
                      {parties.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-indigo-100 text-indigo-800"
                          badgeText={(e.entity_metadata?.role as string) || "PARTY"}
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Authorities */}
                <EntityGroupCard
                  title="Authorities & Institutions"
                  icon={<Building2 className="w-4 h-4 text-amber-600" />}
                  count={authorities.length}
                >
                  {authorities.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No public authorities detected.</p>
                  ) : (
                    <div className="space-y-2">
                      {authorities.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-amber-100 text-amber-800"
                          badgeText="AUTHORITY"
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Reference Numbers */}
                <EntityGroupCard
                  title="Reference Numbers & Case IDs"
                  icon={<Hash className="w-4 h-4 text-purple-600" />}
                  count={references.length}
                >
                  {references.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No reference codes or case numbers found.</p>
                  ) : (
                    <div className="space-y-2">
                      {references.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-purple-100 text-purple-800"
                          badgeText={(e.entity_metadata?.reference_type as string) || "REFERENCE"}
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Legal Citations */}
                <EntityGroupCard
                  title="Statutory References & Legal Sections"
                  icon={<Scale className="w-4 h-4 text-blue-600" />}
                  count={legalSections.length}
                >
                  {legalSections.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No textual legal citations identified.</p>
                  ) : (
                    <div className="space-y-2">
                      {legalSections.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-blue-100 text-blue-800"
                          badgeText="STATUTE REF"
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  )}
                </EntityGroupCard>

                {/* Contact Information */}
                {contacts.length > 0 && (
                  <EntityGroupCard
                    title="Contact Details (Email & Phone)"
                    icon={<Mail className="w-4 h-4 text-cyan-600" />}
                    count={contacts.length}
                  >
                    <div className="space-y-2">
                      {contacts.map((e) => (
                        <EntityItemRow
                          key={e.id}
                          entity={e}
                          badgeColor="bg-cyan-100 text-cyan-800"
                          badgeText={e.entity_type}
                          isSelected={selectedEntity?.id === e.id}
                          onSelect={() => handleSelectEntity(e)}
                        />
                      ))}
                    </div>
                  </EntityGroupCard>
                )}
              </div>
            )}

            {/* TAB 2: Clauses & Sections */}
            {isReady && activeTab === "clauses" && (
              <div className="space-y-3">
                {clauses.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No structured clauses detected.</p>
                ) : (
                  clauses.map((clause) => (
                    <ClauseExplanationCard
                      key={clause.id}
                      documentId={id!}
                      clause={clause}
                      isSelected={selectedClause?.id === clause.id}
                      onSelect={() => handleSelectClause(clause)}
                    />
                  ))
                )}
              </div>
            )}

            {/* TAB 3: Extracted Text Pages */}
            {isReady && activeTab === "raw" && (
              <div className="space-y-3">
                {pages.map((p) => (
                  <div
                    key={p.page_number}
                    className={`border rounded-lg overflow-hidden transition ${
                      activePage === p.page_number ? "border-blue-400 ring-1 ring-blue-400" : "border-slate-200"
                    }`}
                  >
                    <div className="bg-slate-50 px-3 py-1.5 flex items-center justify-between border-b border-slate-200">
                      <span className="text-[11px] font-semibold text-slate-700">Page {p.page_number}</span>
                      <div className="flex items-center gap-2 text-[10px] text-slate-400">
                        {p.ocr_used && (
                          <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium">
                            OCR {p.ocr_confidence != null ? `${(p.ocr_confidence * 100).toFixed(0)}%` : ""}
                          </span>
                        )}
                        {p.width && p.height && <span>{p.width}×{p.height}</span>}
                      </div>
                    </div>
                    <pre className="p-3 text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed max-h-[350px] overflow-auto">
                      {p.text || "(No text extracted)"}
                    </pre>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 4: Semantic Retrieval — Phase 4 Developer Tool */}
            {isReady && activeTab === "retrieval" && id && (
              <SemanticRetrievalPanel
                documentId={id}
                onPageNavigate={(page) => setActivePage(page)}
              />
            )}

            {/* Non-ready loading state */}
            {!status && (
              <div className="flex items-center justify-center py-16 text-slate-400 text-xs gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading document data...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function EntityGroupCard({
  title,
  icon,
  count,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-slate-200 rounded-lg bg-white overflow-hidden shadow-xs">
      <div className="bg-slate-50/80 px-3.5 py-2 border-b border-slate-200 flex items-center justify-between">
        <h4 className="text-xs font-bold text-slate-700 flex items-center gap-2">
          {icon} {title}
        </h4>
        <span className="text-[10px] font-semibold px-2 py-0.5 bg-slate-200 text-slate-700 rounded-full">
          {count}
        </span>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function EntityItemRow({
  entity,
  badgeColor,
  badgeText,
  extraText,
  isSelected,
  onSelect,
}: {
  entity: DocumentEntityItem;
  badgeColor: string;
  badgeText: string;
  extraText?: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition flex items-start justify-between gap-3 ${
        isSelected
          ? "border-blue-500 bg-blue-50/60 shadow-xs"
          : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
      }`}
    >
      <div className="space-y-0.5 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold text-slate-800">{entity.value}</span>
          {extraText && (
            <span className="text-[11px] text-slate-500 font-mono">({extraText})</span>
          )}
        </div>
        <p className="text-[11px] text-slate-500 line-clamp-1 italic font-serif">
          "{entity.source_text}"
        </p>
      </div>

      <div className="flex flex-col items-end gap-1 shrink-0">
        <div className="flex items-center gap-1.5">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${badgeColor}`}>
            {badgeText}
          </span>
          <span className="text-[10px] font-semibold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
            P.{entity.page_number}
          </span>
        </div>
        <span className="text-[9px] text-slate-400">
          {(entity.confidence * 100).toFixed(0)}% conf
        </span>
      </div>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  if (confidence >= 0.9) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
        <CheckCircle2 className="w-3 h-3" /> High ({(confidence * 100).toFixed(0)}%)
      </span>
    );
  }
  if (confidence >= 0.7) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
        <AlertCircle className="w-3 h-3" /> Medium ({(confidence * 100).toFixed(0)}%)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-200 text-slate-700">
      <HelpCircle className="w-3 h-3" /> Low ({(confidence * 100).toFixed(0)}%)
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode }> = {
    READY: { color: "bg-emerald-100 text-emerald-700", icon: <CheckCircle2 className="w-3 h-3" /> },
    READY_WITHOUT_EMBEDDINGS: { color: "bg-amber-100 text-amber-700", icon: <CheckCircle2 className="w-3 h-3" /> },
    FAILED: { color: "bg-red-100 text-red-700", icon: <AlertCircle className="w-3 h-3" /> },
    DELETED: { color: "bg-slate-200 text-slate-500", icon: <Trash2 className="w-3 h-3" /> },
  };

  const entry = map[status] ?? {
    color: "bg-amber-100 text-amber-700",
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${entry.color}`}>
      {entry.icon} {status}
    </span>
  );
}

function formatDocType(raw: string): string {
  if (!raw) return "Unknown Document";
  return raw
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
