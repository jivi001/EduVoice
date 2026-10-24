"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type CaseItem = {
  id: number;
  case_id: string;
  institution_id: number;
  institution_name: string;
  permanent_id: string;
  state: string;
  region: string;
  current_bureau_code: string;
  category: string;
  subject: string;
  status: string;
  received_date: string | null;
  effective_deadline: string | null;
  sla_status: string;
  confidentiality_level: string;
  is_full_access: boolean;
};

type Metrics = {
  total_registered: number;
  total_active: number;
  disposed: number;
  pending: number;
  under_process: number;
  transferred: number;
  escalated: number;
  overdue_active: number;
  approaching_active: number;
  open_cross_bureau_overlaps: number;
};

type OverlapItem = {
  id: number;
  case_1: { id: number; case_id: string; bureau_code: string; status: string; subject: string };
  case_2: { id: number; case_id: string; bureau_code: string; status: string; subject: string };
  institution: { id: number; permanent_id: string; name: string; region: string };
  matching_reason: string;
  alert_status: string;
};

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [overlaps, setOverlaps] = useState<OverlapItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [selectedBureau, setSelectedBureau] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedRegion, setSelectedRegion] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [overlapOnly, setOverlapOnly] = useState(false);

  const loadDashboard = useCallback(() => {
    setLoading(true);
    // 1. Load Metrics
    api<Metrics>("/dashboard/metrics")
      .then(setMetrics)
      .catch(() => {});

    // 2. Load Open Overlaps
    api<OverlapItem[]>("/overlaps?status=OPEN")
      .then(setOverlaps)
      .catch(() => {});

    // 3. Load Cases
    const params = new URLSearchParams();
    if (search.trim()) params.append("search", search.trim());
    if (selectedBureau) params.append("bureau_id", selectedBureau);
    if (selectedStatus) params.append("status", selectedStatus);
    if (selectedRegion) params.append("region", selectedRegion);
    if (overdueOnly) params.append("overdue_only", "true");
    if (overlapOnly) params.append("overlap_only", "true");

    api<{ cases: CaseItem[]; total: number }>(`/cases?${params.toString()}`)
      .then((res) => setCases(res.cases))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, selectedBureau, selectedStatus, selectedRegion, overdueOnly, overlapOnly]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Pending":
        return <span style={{ background: "#e2e8f0", color: "#334155", padding: "3px 8px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>Pending</span>;
      case "Under Process":
        return <span style={{ background: "#dbeafe", color: "#1d4ed8", padding: "3px 8px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>Under Process</span>;
      case "Transferred":
        return <span style={{ background: "#ffedd5", color: "#c2410c", padding: "3px 8px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>Transferred</span>;
      case "Escalated":
        return <span style={{ background: "#fee2e2", color: "#b91c1c", padding: "3px 8px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>Escalated</span>;
      case "Disposed":
        return <span style={{ background: "#dcfce7", color: "#15803d", padding: "3px 8px", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 600 }}>Disposed</span>;
      default:
        return <span>{status}</span>;
    }
  };

  const getSlaBadge = (sla: string, deadline: string | null) => {
    if (sla === "OVERDUE") {
      return <span style={{ background: "#b91c1c", color: "white", padding: "2px 8px", borderRadius: "10px", fontSize: "0.75rem", fontWeight: 700 }}>OVERDUE</span>;
    }
    if (sla === "APPROACHING") {
      return <span style={{ background: "#f59e0b", color: "white", padding: "2px 8px", borderRadius: "10px", fontSize: "0.75rem", fontWeight: 700 }}>DUE SOON</span>;
    }
    if (sla === "ON_TRACK") {
      return <span style={{ background: "#10b981", color: "white", padding: "2px 8px", borderRadius: "10px", fontSize: "0.75rem", fontWeight: 600 }}>ON TRACK</span>;
    }
    if (sla === "DISPOSED") {
      return <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>Completed</span>;
    }
    return <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>No SLA</span>;
  };

  return (
    <Shell wide>
      {(me: Me) => (
        <div>
          {/* Header Title & Actions */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>EduVoice: Integrated Complaint Dashboard</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                Consolidated cross-bureau monitoring, duplicate detection, and SLA oversight across Regulation, PGRC, and Approval Bureaus.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.6rem" }}>
              <button className="btn quiet" onClick={loadDashboard}>
                🔄 Refresh
              </button>
              <a href="/cases/new" className="btn" style={{ textDecoration: "none" }}>
                + Register New Case
              </a>
            </div>
          </div>

          {/* Metrics Overview Cards */}
          {metrics && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.8rem", marginBottom: "1.5rem" }}>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Registered</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "var(--ink)" }}>{metrics.total_registered}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Active Cases</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "var(--stamp)" }}>{metrics.total_active}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Pending</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0" }}>{metrics.pending}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Under Process</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#1d4ed8" }}>{metrics.under_process}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Transferred</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#c2410c" }}>{metrics.transferred}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Escalated</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#b91c1c" }}>{metrics.escalated}</h3>
              </div>
              <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Disposed</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#15803d" }}>{metrics.disposed}</h3>
              </div>
              <div style={{ background: "#fef2f2", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid #fca5a5" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#991b1b", textTransform: "uppercase" }}>Overdue</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#991b1b" }}>{metrics.overdue_active}</h3>
              </div>
              <div style={{ background: "#fdf2f8", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid #f472b6" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#9d174d", textTransform: "uppercase" }}>Overlaps</span>
                <h3 style={{ fontSize: "1.8rem", margin: "0.2rem 0 0 0", color: "#9d174d" }}>{metrics.open_cross_bureau_overlaps}</h3>
              </div>
            </div>
          )}

          {/* Cross-Bureau Overlaps Banner */}
          {overlaps.length > 0 && (
            <div
              style={{
                background: "#fdf4ff",
                border: "2px solid #d946ef",
                borderRadius: "var(--r-md)",
                padding: "1rem 1.4rem",
                marginBottom: "1.5rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ margin: 0, color: "#86198f", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    ⚠️ {overlaps.length} Active Cross-Bureau Overlap Incident{overlaps.length > 1 ? "s" : ""} Flagged
                  </h3>
                  <p style={{ margin: "0.3rem 0 0 0", color: "#701a75", fontSize: "0.9rem" }}>
                    Multiple AICTE bureaus are handling parallel grievances for the same technical institution. Review to prevent redundant proceedings.
                  </p>
                </div>
                <a href="/overlaps" className="btn" style={{ background: "#a21caf", textDecoration: "none", fontSize: "0.88rem" }}>
                  Review Overlaps &rarr;
                </a>
              </div>
              <div style={{ marginTop: "0.8rem", display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
                {overlaps.map((o) => (
                  <div key={o.id} style={{ background: "white", border: "1px solid #f0abfc", borderRadius: "var(--r-sm)", padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}>
                    <strong>{o.institution.name}</strong> ({o.institution.permanent_id}):{" "}
                    <span style={{ color: "#a21caf", fontWeight: 600 }}>
                      {o.case_1.case_id} ({o.case_1.bureau_code}) &harr; {o.case_2.case_id} ({o.case_2.bureau_code})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Filter Bar */}
          <div
            style={{
              background: "var(--panel)",
              padding: "1rem",
              borderRadius: "var(--r-md)",
              border: "1px solid var(--line-strong)",
              marginBottom: "1.2rem",
              display: "flex",
              flexWrap: "wrap",
              gap: "0.8rem",
              alignItems: "center",
            }}
          >
            <input
              type="text"
              placeholder="Search Case ID or Permanent ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: "1 1 220px", padding: "0.55rem 0.8rem" }}
            />

            <select value={selectedBureau} onChange={(e) => setSelectedBureau(e.target.value)} style={{ flex: "0 1 150px" }}>
              <option value="">All Bureaus</option>
              <option value="1">Regulation (RB)</option>
              <option value="2">Public Grievance (PGRC)</option>
              <option value="3">Approval (AB)</option>
            </select>

            <select value={selectedStatus} onChange={(e) => setSelectedStatus(e.target.value)} style={{ flex: "0 1 150px" }}>
              <option value="">All Statuses</option>
              <option value="Pending">Pending</option>
              <option value="Under Process">Under Process</option>
              <option value="Transferred">Transferred</option>
              <option value="Escalated">Escalated</option>
              <option value="Disposed">Disposed</option>
            </select>

            <select value={selectedRegion} onChange={(e) => setSelectedRegion(e.target.value)} style={{ flex: "0 1 150px" }}>
              <option value="">All Regions</option>
              <option value="Northern">Northern</option>
              <option value="Western">Western</option>
              <option value="Southern">Southern</option>
              <option value="Eastern">Eastern</option>
              <option value="South-West">South-West</option>
              <option value="North-West">North-West</option>
            </select>

            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", margin: 0, fontSize: "0.85rem", cursor: "pointer" }}>
              <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
              Overdue Only
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", margin: 0, fontSize: "0.85rem", cursor: "pointer" }}>
              <input type="checkbox" checked={overlapOnly} onChange={(e) => setOverlapOnly(e.target.checked)} />
              Overlap Only
            </label>
          </div>

          {/* Cases Table */}
          <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", overflowX: "auto" }}>
            {loading ? (
              <p className="muted" style={{ padding: "2rem", textAlign: "center" }}>Loading complaint cases…</p>
            ) : !cases.length ? (
              <div style={{ padding: "3rem 1rem", textAlign: "center" }}>
                <p className="muted" style={{ margin: 0 }}>No cases found matching your filters.</p>
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
                <thead>
                  <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--line-strong)", textAlign: "left" }}>
                    <th style={{ padding: "0.75rem 1rem" }}>Case ID</th>
                    <th style={{ padding: "0.75rem 1rem" }}>Institution</th>
                    <th style={{ padding: "0.75rem 1rem" }}>Bureau</th>
                    <th style={{ padding: "0.75rem 1rem" }}>Category & Subject</th>
                    <th style={{ padding: "0.75rem 1rem" }}>Status</th>
                    <th style={{ padding: "0.75rem 1rem" }}>SLA & Deadline</th>
                    <th style={{ padding: "0.75rem 1rem", textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.id} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td style={{ padding: "0.75rem 1rem", fontWeight: 700 }}>
                        <a href={`/cases/${c.id}`} style={{ textDecoration: "none", color: "var(--stamp)" }}>
                          {c.case_id}
                        </a>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <div style={{ fontWeight: 600 }}>{c.institution_name}</div>
                        <div className="muted" style={{ fontSize: "0.78rem" }}>
                          {c.permanent_id} &bull; {c.state} ({c.region})
                        </div>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "2px 8px", borderRadius: "10px", fontSize: "0.8rem", fontWeight: 700 }}>
                          {c.current_bureau_code}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem 1rem", maxWidth: "300px" }}>
                        <div style={{ fontWeight: 600, color: "var(--ink)" }}>{c.category}</div>
                        <div style={{ color: "var(--ink-soft)", fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.subject}
                        </div>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>{getStatusBadge(c.status)}</td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <div style={{ marginBottom: "2px" }}>{getSlaBadge(c.sla_status, c.effective_deadline)}</div>
                        {c.effective_deadline && c.status !== "Disposed" && (
                          <div className="muted" style={{ fontSize: "0.75rem" }}>
                            Due: {new Date(c.effective_deadline).toLocaleDateString()}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "0.75rem 1rem", textAlign: "right" }}>
                        <a href={`/cases/${c.id}`} className="btn quiet" style={{ padding: "0.35rem 0.75rem", fontSize: "0.82rem", textDecoration: "none" }}>
                          View
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </Shell>
  );
}
