"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type OverlapRow = {
  id: number;
  case_1: { id: number; case_id: string; bureau_code: string; status: string; subject: string };
  case_2: { id: number; case_id: string; bureau_code: string; status: string; subject: string };
  institution: { id: number; permanent_id: string; name: string; state: string; region: string };
  relationship_type: string;
  review_status: string;
  alert_status: string;
  matching_reason: string;
  detected_at: string;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  resolution_reason: string | null;
};

export default function OverlapsPage() {
  const [overlaps, setOverlaps] = useState<OverlapRow[]>([]);
  const [filterStatus, setFilterStatus] = useState("OPEN");
  const [loading, setLoading] = useState(true);

  const loadOverlaps = useCallback(() => {
    setLoading(true);
    api<OverlapRow[]>(`/overlaps?status=${filterStatus}`)
      .then(setOverlaps)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filterStatus]);

  useEffect(() => {
    loadOverlaps();
  }, [loadOverlaps]);

  async function handleReview(id: number, review_status: "CONFIRMED_RELATED" | "DISMISSED") {
    await api(`/overlaps/${id}/review`, {
      method: "POST",
      body: { review_status, resolution_reason: `Reviewed by officer: ${review_status}` },
    });
    loadOverlaps();
  }

  return (
    <Shell wide>
      {(me: Me) => (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>Cross-Bureau Overlap Tracking</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                AICTE Smart Overlap Engine: Synchronously detects and synchronizes concurrent grievances for the same institution across cells.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.4rem" }}>
              <button
                className={`btn ${filterStatus === "OPEN" ? "" : "quiet"}`}
                onClick={() => setFilterStatus("OPEN")}
                style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}
              >
                Active Incidents ({filterStatus === "OPEN" ? overlaps.length : ""})
              </button>
              <button
                className={`btn ${filterStatus === "RESOLVED" ? "" : "quiet"}`}
                onClick={() => setFilterStatus("RESOLVED")}
                style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}
              >
                Auto-Resolved
              </button>
              <button
                className={`btn ${filterStatus === "ALL" ? "" : "quiet"}`}
                onClick={() => setFilterStatus("ALL")}
                style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}
              >
                All Overlaps
              </button>
            </div>
          </div>

          {loading ? (
            <p className="muted" style={{ textAlign: "center", padding: "2rem" }}>Loading overlap incidents…</p>
          ) : !overlaps.length ? (
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "3rem", textAlign: "center" }}>
              <h3 style={{ margin: 0, color: "#15803d" }}>✓ No Open Cross-Bureau Overlaps</h3>
              <p className="muted" style={{ margin: "0.4rem 0 0 0" }}>All bureaus are currently processing isolated or non-overlapping cases.</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {overlaps.map((o) => (
                <div
                  key={o.id}
                  style={{
                    background: "var(--panel)",
                    borderRadius: "var(--r-md)",
                    border: o.alert_status === "OPEN" ? "2px solid #d946ef" : "1px solid var(--line-strong)",
                    padding: "1.2rem",
                    boxShadow: "var(--shadow-1)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.8rem" }}>
                    <div>
                      <span style={{ fontSize: "0.8rem", color: "var(--muted)", fontWeight: 600 }}>INSTITUTION AFFECTED</span>
                      <h3 style={{ fontSize: "1.25rem", margin: "0.1rem 0" }}>{o.institution.name}</h3>
                      <div style={{ fontSize: "0.85rem" }}>
                        Permanent ID: <code>{o.institution.permanent_id}</code> &bull; Region: {o.institution.region} ({o.institution.state})
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <span
                        style={{
                          background: o.alert_status === "OPEN" ? "#fdf4ff" : "#f1f5f9",
                          color: o.alert_status === "OPEN" ? "#86198f" : "#475569",
                          border: o.alert_status === "OPEN" ? "1px solid #f0abfc" : "1px solid #cbd5e1",
                          borderRadius: "12px",
                          padding: "2px 8px",
                          fontSize: "0.78rem",
                          fontWeight: 700,
                        }}
                      >
                        {o.alert_status}
                      </span>
                      <span style={{ fontSize: "0.78rem", background: "var(--paper)", padding: "2px 8px", borderRadius: "12px" }}>
                        Review: {o.review_status}
                      </span>
                    </div>
                  </div>

                  <div style={{ background: "var(--paper)", padding: "0.6rem 0.9rem", borderRadius: "var(--r-sm)", fontSize: "0.88rem", marginBottom: "1rem", color: "var(--ink-soft)" }}>
                    🔍 <strong>Matching Trigger:</strong> {o.matching_reason}
                  </div>

                  {/* Case Pair Grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                    <div style={{ background: "white", border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "0.8rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                        <a href={`/cases/${o.case_1.id}`} style={{ fontWeight: 700, color: "var(--stamp)", textDecoration: "none" }}>
                          {o.case_1.case_id}
                        </a>
                        <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "1px 6px", borderRadius: "6px", fontSize: "0.75rem", fontWeight: 700 }}>
                          Bureau {o.case_1.bureau_code}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.88rem", fontWeight: 600 }}>{o.case_1.subject}</div>
                      <span className="muted" style={{ fontSize: "0.78rem" }}>Status: {o.case_1.status}</span>
                    </div>

                    <div style={{ background: "white", border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "0.8rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                        <a href={`/cases/${o.case_2.id}`} style={{ fontWeight: 700, color: "var(--stamp)", textDecoration: "none" }}>
                          {o.case_2.case_id}
                        </a>
                        <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "1px 6px", borderRadius: "6px", fontSize: "0.75rem", fontWeight: 700 }}>
                          Bureau {o.case_2.bureau_code}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.88rem", fontWeight: 600 }}>{o.case_2.subject}</div>
                      <span className="muted" style={{ fontSize: "0.78rem" }}>Status: {o.case_2.status}</span>
                    </div>
                  </div>

                  {o.resolution_reason && (
                    <div style={{ fontSize: "0.82rem", color: "#15803d", marginBottom: "0.6rem" }}>
                      ✓ <strong>Resolution Notes:</strong> {o.resolution_reason}
                    </div>
                  )}

                  {o.alert_status === "OPEN" && (
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", borderTop: "1px solid var(--line)", paddingTop: "0.8rem" }}>
                      <button className="btn quiet" onClick={() => handleReview(o.id, "CONFIRMED_RELATED")} style={{ fontSize: "0.82rem", padding: "0.3rem 0.8rem" }}>
                        Confirm Related Case
                      </button>
                      <button className="btn quiet" onClick={() => handleReview(o.id, "DISMISSED")} style={{ fontSize: "0.82rem", padding: "0.3rem 0.8rem", color: "var(--alert)" }}>
                        Dismiss Overlap Alert
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
