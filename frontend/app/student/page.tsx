"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type StudentComplaint = {
  id: number;
  case_id: string;
  institution_name: string;
  permanent_id: string;
  category: string;
  subject: string;
  status: string;
  received_date: string;
  effective_deadline: string | null;
  sla_status: string;
  last_action: string | null;
};

export default function StudentHome() {
  const [complaints, setComplaints] = useState<StudentComplaint[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [permId, setPermId] = useState("");
  const [category, setCategory] = useState("Fee Refund");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [phone, setPhone] = useState("");
  const [confidentiality, setConfidentiality] = useState("ORDINARY");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const loadComplaints = useCallback(() => {
    setLoading(true);
    api<StudentComplaint[]>("/student/complaints")
      .then(setComplaints)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadComplaints();
  }, [loadComplaints]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const res = await api<{ case_id: string; message: string }>("/student/complaints", {
        method: "POST",
        body: {
          permanent_id: permId.trim(),
          category,
          subject: subject.trim(),
          description: description.trim(),
          phone: phone.trim() || null,
          confidentiality_level: confidentiality,
        },
      });
      setMsg({ ok: true, text: `Grievance submitted successfully! Official Tracking ID: ${res.case_id}` });
      setShowForm(false);
      setPermId("");
      setSubject("");
      setDescription("");
      setPhone("");
      loadComplaints();
    } catch (err: any) {
      setMsg({ ok: false, text: err.message || "Failed to submit grievance." });
    } finally {
      setBusy(false);
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Pending":
        return <span style={{ background: "#e2e8f0", color: "#334155", padding: "2px 8px", borderRadius: "10px", fontSize: "0.78rem", fontWeight: 600 }}>Pending Review</span>;
      case "Under Process":
        return <span style={{ background: "#dbeafe", color: "#1d4ed8", padding: "2px 8px", borderRadius: "10px", fontSize: "0.78rem", fontWeight: 600 }}>Under Process</span>;
      case "Transferred":
        return <span style={{ background: "#ffedd5", color: "#c2410c", padding: "2px 8px", borderRadius: "10px", fontSize: "0.78rem", fontWeight: 600 }}>Transferred</span>;
      case "Escalated":
        return <span style={{ background: "#fee2e2", color: "#b91c1c", padding: "2px 8px", borderRadius: "10px", fontSize: "0.78rem", fontWeight: 600 }}>Escalated to Supervisor</span>;
      case "Disposed":
        return <span style={{ background: "#dcfce7", color: "#15803d", padding: "2px 8px", borderRadius: "10px", fontSize: "0.78rem", fontWeight: 600 }}>Resolved & Disposed</span>;
      default:
        return <span>{status}</span>;
    }
  };

  return (
    <Shell role="student">
      {(me: Me) => (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>Student Grievance Portal</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                Welcome, {me.name}. Lodge official AICTE grievances against institutions and track live resolution progress.
              </p>
            </div>
            <button className="btn" onClick={() => setShowForm(!showForm)}>
              {showForm ? "Cancel" : "+ Lodge New Grievance"}
            </button>
          </div>

          {msg && (
            <div style={{ padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", marginBottom: "1rem", background: msg.ok ? "var(--sealed-soft)" : "var(--alert-soft)", color: msg.ok ? "var(--sealed)" : "var(--alert)", fontWeight: 600 }}>
              {msg.text}
            </div>
          )}

          {/* New Grievance Form */}
          {showForm && (
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "2px solid var(--stamp)", padding: "1.5rem", marginBottom: "1.5rem", boxShadow: "var(--shadow-2)" }}>
              <h2 style={{ fontSize: "1.3rem", margin: "0 0 0.8rem 0" }}>Lodge Grievance with AICTE</h2>
              <p className="muted" style={{ margin: "0 0 1rem 0", fontSize: "0.85rem" }}>
                Your grievance is automatically routed to the Public Grievance Redressal Cell (PGRC) with a unique AICTE tracking ID.
              </p>

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.9rem" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div>
                    <label>Institution AICTE Permanent ID *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. 1-10928374"
                      value={permId}
                      onChange={(e) => setPermId(e.target.value)}
                    />
                    <span className="muted" style={{ fontSize: "0.75rem" }}>Demo: 1-10928374 (Apex), 1-20938475 (Western), 1-30948576 (Bangalore)</span>
                  </div>

                  <div>
                    <label>Grievance Category *</label>
                    <select value={category} onChange={(e) => setCategory(e.target.value)}>
                      <option value="Fee Refund">Fee Refund / Excess Fee</option>
                      <option value="Capitation Fee">Capitation Fee Demand</option>
                      <option value="Ragging">Ragging / Harassment</option>
                      <option value="Infrastructure Deficiency">Inadequate Lab / Infrastructure</option>
                      <option value="Faculty Harassment">Faculty / Staff Harassment</option>
                      <option value="Admission Irregularity">Admission Irregularity</option>
                      <option value="General Grievance">General Grievance</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div>
                    <label>Contact Phone (Optional)</label>
                    <input type="text" placeholder="+91..." value={phone} onChange={(e) => setPhone(e.target.value)} />
                  </div>
                  <div>
                    <label>Confidentiality Level</label>
                    <select value={confidentiality} onChange={(e) => setConfidentiality(e.target.value)}>
                      <option value="ORDINARY">Ordinary Grievance</option>
                      <option value="HIGH">High Confidentiality (Identity Protected Whistleblower)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label>Grievance Subject *</label>
                  <input
                    type="text"
                    required
                    placeholder="Brief summary of the issue..."
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </div>

                <div>
                  <label>Detailed Explanation of Grievance *</label>
                  <textarea
                    rows={4}
                    required
                    placeholder="Provide specific dates, facts, demand notices, or incidents..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem" }}>
                  <button type="button" className="btn quiet" onClick={() => setShowForm(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn" disabled={busy}>
                    {busy ? "Submitting to AICTE…" : "Submit Grievance"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Submitted Grievances List */}
          <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.2rem" }}>
            <h2 style={{ fontSize: "1.2rem", margin: "0 0 0.8rem 0" }}>My Registered Grievances & Progress</h2>
            {loading ? (
              <p className="muted">Loading your grievance tracking records…</p>
            ) : !complaints.length ? (
              <div style={{ textAlign: "center", padding: "2rem" }}>
                <p className="muted" style={{ margin: 0 }}>You haven't filed any grievances yet.</p>
                <button className="btn quiet" onClick={() => setShowForm(true)} style={{ marginTop: "0.6rem", fontSize: "0.85rem" }}>
                  + File a Grievance
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                {complaints.map((c) => (
                  <div key={c.id} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "1rem", background: "var(--paper-raised)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.4rem" }}>
                      <div>
                        <span style={{ fontWeight: 700, color: "var(--stamp)", fontSize: "1.05rem" }}>{c.case_id}</span>
                        <span className="muted" style={{ marginLeft: "0.8rem", fontSize: "0.85rem" }}>
                          Institution: <strong>{c.institution_name}</strong> (<code>{c.permanent_id}</code>)
                        </span>
                      </div>
                      <div>{getStatusBadge(c.status)}</div>
                    </div>

                    <div style={{ fontWeight: 600, fontSize: "0.95rem", color: "var(--ink)", marginBottom: "0.3rem" }}>
                      [{c.category}] {c.subject}
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--ink-soft)", borderTop: "1px solid var(--line)", paddingTop: "0.4rem", marginTop: "0.4rem" }}>
                      <span>Submitted: {c.received_date}</span>
                      {c.effective_deadline && <span>SLA Target: {new Date(c.effective_deadline).toLocaleDateString()}</span>}
                      {c.last_action && <span>Latest Action: <em>{c.last_action}</em></span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
