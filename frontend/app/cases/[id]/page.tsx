"use client";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type HistoryEntry = {
  id: number;
  action_type: string;
  actor_name: string;
  previous_status: string | null;
  new_status: string | null;
  source_bureau_code: string | null;
  destination_bureau_code: string | null;
  action_summary: string;
  restricted_remarks: string | null;
  event_visibility: string;
  created_at: string;
};

type OverlapEntry = {
  id: number;
  paired_case_id: string;
  paired_bureau: string;
  alert_status: string;
  review_status: string;
  matching_reason: string;
};

type CaseDetail = {
  id: number;
  case_id: string;
  institution_id: number;
  institution_name: string;
  permanent_id: string;
  state: string;
  region: string;
  current_bureau_id: number;
  current_bureau_code: string;
  current_bureau_name: string;
  confidentiality_level: string;
  is_full_access: boolean;
  category: string;
  subject: string;
  description: string;
  complainant_type: string;
  complainant_name: string | null;
  complainant_email: string | null;
  complainant_phone: string | null;
  status: string;
  received_date: string | null;
  created_at: string | null;
  effective_deadline: string | null;
  sla_status: string;
  assigned_officer_id: number | null;
  assigned_officer_name: string | null;
  last_action: string | null;
  history: HistoryEntry[];
  overlaps: OverlapEntry[];
};

export default function CaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params?.id;

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Modals state
  const [modalMode, setModalMode] = useState<"transfer" | "escalate" | "dispose" | "assign" | null>(null);
  const [destBureau, setDestBureau] = useState("1");
  const [reason, setReason] = useState("");
  const [remarks, setRemarks] = useState("");

  const loadCase = useCallback(() => {
    if (!caseId) return;
    setLoading(true);
    api<CaseDetail>(`/cases/${caseId}`)
      .then(setCaseData)
      .catch((err) => setActionMsg({ ok: false, text: err.message }))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  async function handleTransfer() {
    try {
      await api(`/cases/${caseId}/transfer`, {
        method: "POST",
        body: { destination_bureau_id: Number(destBureau), reason, restricted_remarks: remarks },
      });
      setModalMode(null);
      setReason("");
      setRemarks("");
      loadCase();
      setActionMsg({ ok: true, text: "Case transferred successfully." });
    } catch (err: any) {
      setActionMsg({ ok: false, text: err.message });
    }
  }

  async function handleAcceptTransfer() {
    try {
      await api(`/cases/${caseId}/accept-transfer`, { method: "POST" });
      loadCase();
      setActionMsg({ ok: true, text: "Transfer accepted. Case is now Under Process." });
    } catch (err: any) {
      setActionMsg({ ok: false, text: err.message });
    }
  }

  async function handleEscalate() {
    try {
      await api(`/cases/${caseId}/escalate`, {
        method: "POST",
        body: { reason, restricted_remarks: remarks },
      });
      setModalMode(null);
      setReason("");
      setRemarks("");
      loadCase();
      setActionMsg({ ok: true, text: "Case escalated to supervisor queue." });
    } catch (err: any) {
      setActionMsg({ ok: false, text: err.message });
    }
  }

  async function handleAckEscalation() {
    try {
      await api(`/cases/${caseId}/acknowledge-escalation`, { method: "POST" });
      loadCase();
      setActionMsg({ ok: true, text: "Escalation acknowledged. Case returned to Under Process." });
    } catch (err: any) {
      setActionMsg({ ok: false, text: err.message });
    }
  }

  async function handleDispose() {
    try {
      await api(`/cases/${caseId}/dispose`, {
        method: "POST",
        body: { resolution_summary: reason, restricted_remarks: remarks },
      });
      setModalMode(null);
      setReason("");
      setRemarks("");
      loadCase();
      setActionMsg({ ok: true, text: "Case disposed successfully. Active overlap alerts resolved." });
    } catch (err: any) {
      setActionMsg({ ok: false, text: err.message });
    }
  }

  return (
    <Shell wide>
      {(me: Me) => {
        if (loading) return <p className="muted" style={{ padding: "2rem" }}>Loading case records…</p>;
        if (!caseData) return <p className="muted" style={{ padding: "2rem" }}>Case not found.</p>;

        const isDisposed = caseData.status === "Disposed";
        const hasOpenOverlaps = caseData.overlaps.some((o) => o.alert_status === "OPEN");

        return (
          <div style={{ maxWidth: "1050px", margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <button className="link" onClick={() => router.back()} style={{ fontSize: "0.9rem" }}>
                &larr; Back to Cases
              </button>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "3px 10px", borderRadius: "12px", fontSize: "0.85rem", fontWeight: 700 }}>
                  Bureau: {caseData.current_bureau_code}
                </span>
                <span style={{ background: "#e0f2fe", color: "#0369a1", padding: "3px 10px", borderRadius: "12px", fontSize: "0.85rem", fontWeight: 600 }}>
                  Status: {caseData.status}
                </span>
                {caseData.confidentiality_level === "HIGH" && (
                  <span style={{ background: "#fee2e2", color: "#b91c1c", padding: "3px 10px", borderRadius: "12px", fontSize: "0.85rem", fontWeight: 700 }}>
                    HIGH CONFIDENTIALITY
                  </span>
                )}
              </div>
            </div>

            {actionMsg && (
              <div style={{ padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", marginBottom: "1rem", background: actionMsg.ok ? "var(--sealed-soft)" : "var(--alert-soft)", color: actionMsg.ok ? "var(--sealed)" : "var(--alert)", fontWeight: 600 }}>
                {actionMsg.text}
              </div>
            )}

            {/* Overlap Warning Banner */}
            {hasOpenOverlaps && (
              <div style={{ background: "#fdf4ff", border: "2px solid #d946ef", borderRadius: "var(--r-md)", padding: "1rem", marginBottom: "1.2rem" }}>
                <h3 style={{ margin: 0, color: "#86198f" }}>⚠️ Active Cross-Bureau Overlap Flagged</h3>
                <p style={{ margin: "0.3rem 0 0.5rem 0", color: "#701a75", fontSize: "0.88rem" }}>
                  This institution has concurrent open proceedings in another AICTE division:
                </p>
                {caseData.overlaps.filter((o) => o.alert_status === "OPEN").map((o) => (
                  <div key={o.id} style={{ background: "white", padding: "0.4rem 0.8rem", borderRadius: "var(--r-sm)", border: "1px solid #f0abfc", fontSize: "0.85rem" }}>
                    Paired Case: <strong>{o.paired_case_id}</strong> (Bureau {o.paired_bureau}) &bull; Reason: {o.matching_reason}
                  </div>
                ))}
              </div>
            )}

            {/* Main Case Info Card */}
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.5rem", marginBottom: "1.5rem" }}>
              <div style={{ borderBottom: "1px solid var(--line)", paddingBottom: "1rem", marginBottom: "1rem" }}>
                <span className="muted" style={{ fontSize: "0.85rem" }}>AICTE Grievance Tracking ID</span>
                <h1 style={{ fontSize: "2rem", margin: "0.1rem 0 0.4rem 0", color: "var(--ink)" }}>{caseData.case_id}</h1>
                <div style={{ fontSize: "0.95rem" }}>
                  <strong>{caseData.institution_name}</strong> &bull; Permanent ID: <code>{caseData.permanent_id}</code> &bull; Region: {caseData.region} ({caseData.state})
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.2rem", fontSize: "0.9rem" }}>
                <div>
                  <span className="muted">Category:</span>
                  <div style={{ fontWeight: 600 }}>{caseData.category}</div>
                </div>
                <div>
                  <span className="muted">Received Date:</span>
                  <div style={{ fontWeight: 600 }}>{caseData.received_date || "N/A"}</div>
                </div>
                <div>
                  <span className="muted">Effective SLA Deadline:</span>
                  <div style={{ fontWeight: 600 }}>
                    {caseData.effective_deadline ? new Date(caseData.effective_deadline).toLocaleDateString() : "No SLA"} ({caseData.sla_status})
                  </div>
                </div>
                <div>
                  <span className="muted">Assigned Officer:</span>
                  <div style={{ fontWeight: 600 }}>{caseData.assigned_officer_name || "Unassigned"}</div>
                </div>
              </div>

              {caseData.is_full_access && caseData.complainant_name && (
                <div style={{ background: "var(--paper)", padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", marginBottom: "1.2rem", fontSize: "0.88rem" }}>
                  <strong>Complainant ({caseData.complainant_type}):</strong> {caseData.complainant_name}{" "}
                  {caseData.complainant_email && <span>&bull; {caseData.complainant_email}</span>}
                  {caseData.complainant_phone && <span>&bull; {caseData.complainant_phone}</span>}
                </div>
              )}

              <div style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ margin: "0 0 0.4rem 0" }}>Subject</h3>
                <p style={{ margin: "0 0 1rem 0", fontWeight: 500 }}>{caseData.subject}</p>
                <h3 style={{ margin: "0 0 0.4rem 0" }}>Case Narrative / Details</h3>
                <div style={{ background: "var(--paper-raised)", padding: "1rem", borderRadius: "var(--r-sm)", border: "1px solid var(--line)", whiteSpace: "pre-wrap", fontSize: "0.92rem", lineHeight: 1.6 }}>
                  {caseData.description}
                </div>
              </div>

              {/* Action Toolbar */}
              {!isDisposed && (
                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "1rem", display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
                  <button className="btn quiet" onClick={() => setModalMode("transfer")}>
                    ⇄ Transfer Bureau
                  </button>
                  {caseData.status === "Transferred" && (
                    <button className="btn" onClick={handleAcceptTransfer}>
                      ✓ Accept Transfer
                    </button>
                  )}
                  <button className="btn quiet" onClick={() => setModalMode("escalate")}>
                    ▲ Escalate
                  </button>
                  {caseData.status === "Escalated" && (
                    <button className="btn" onClick={handleAckEscalation}>
                      ✓ Acknowledge Escalation
                    </button>
                  )}
                  {caseData.status !== "Pending" && (
                    <button className="btn danger" onClick={() => setModalMode("dispose")}>
                      ✕ Dispose Case
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Action Modals */}
            {modalMode && (
              <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "1rem" }}>
                <div style={{ background: "white", padding: "1.5rem", borderRadius: "var(--r-md)", width: "100%", maxWidth: "500px", boxShadow: "var(--shadow-2)" }}>
                  <h2 style={{ margin: "0 0 1rem 0" }}>
                    {modalMode === "transfer" && "Transfer Case to Bureau"}
                    {modalMode === "escalate" && "Escalate Case to Supervisor"}
                    {modalMode === "dispose" && "Dispose Case with Resolution"}
                  </h2>

                  {modalMode === "transfer" && (
                    <div style={{ marginBottom: "1rem" }}>
                      <label>Target Destination Bureau:</label>
                      <select value={destBureau} onChange={(e) => setDestBureau(e.target.value)}>
                        <option value="1">Regulation Bureau (RB)</option>
                        <option value="2">Public Grievance Redressal Cell (PGRC)</option>
                        <option value="3">Approval Bureau (AB)</option>
                      </select>
                    </div>
                  )}

                  <div style={{ marginBottom: "1rem" }}>
                    <label>{modalMode === "dispose" ? "Resolution Summary (Required):" : "Official Reason (Required):"}</label>
                    <textarea rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Provide accountable explanation..." />
                  </div>

                  <div style={{ marginBottom: "1.2rem" }}>
                    <label>Internal Restricted Remarks (Never exposed cross-bureau):</label>
                    <textarea rows={2} value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Confidential committee notes..." />
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem" }}>
                    <button className="btn quiet" onClick={() => setModalMode(null)}>Cancel</button>
                    {modalMode === "transfer" && <button className="btn" disabled={!reason.trim()} onClick={handleTransfer}>Confirm Transfer</button>}
                    {modalMode === "escalate" && <button className="btn" disabled={!reason.trim()} onClick={handleEscalate}>Confirm Escalation</button>}
                    {modalMode === "dispose" && <button className="btn danger" disabled={!reason.trim()} onClick={handleDispose}>Confirm Disposal</button>}
                  </div>
                </div>
              </div>
            )}

            {/* Action History / Audit Trail Timeline */}
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.5rem" }}>
              <h2 style={{ fontSize: "1.3rem", margin: "0 0 1rem 0" }}>Chronological Action History & Audit Trail</h2>
              {!caseData.history.length ? (
                <p className="muted">No history entries recorded.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {caseData.history.map((h, i) => (
                    <div key={h.id} style={{ display: "flex", gap: "1rem", position: "relative" }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: "var(--stamp)", marginTop: "4px" }} />
                        {i < caseData.history.length - 1 && (
                          <div style={{ width: "2px", flexGrow: 1, background: "var(--line-strong)", margin: "4px 0" }} />
                        )}
                      </div>
                      <div style={{ flexGrow: 1, background: "var(--paper)", padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", border: "1px solid var(--line)" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                          <strong style={{ color: "var(--stamp-deep)" }}>{h.action_type}</strong>
                          <span className="muted" style={{ fontSize: "0.78rem" }}>
                            {new Date(h.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.85rem", color: "var(--ink-soft)" }}>
                          Actor: <strong>{h.actor_name}</strong>
                          {h.previous_status && h.new_status && (
                            <span> &bull; Status: {h.previous_status} &rarr; <strong>{h.new_status}</strong></span>
                          )}
                          {h.source_bureau_code && h.destination_bureau_code && h.source_bureau_code !== h.destination_bureau_code && (
                            <span> &bull; Bureau: {h.source_bureau_code} &rarr; <strong>{h.destination_bureau_code}</strong></span>
                          )}
                        </div>
                        <p style={{ margin: "0.4rem 0 0 0", fontSize: "0.9rem" }}>{h.action_summary}</p>
                        {h.restricted_remarks && (
                          <div style={{ marginTop: "0.4rem", padding: "0.4rem 0.6rem", background: "white", borderLeft: "3px solid var(--gold)", fontSize: "0.82rem", color: "var(--ink)" }}>
                            🔒 <strong>Restricted Remarks:</strong> {h.restricted_remarks}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      }}
    </Shell>
  );
}
