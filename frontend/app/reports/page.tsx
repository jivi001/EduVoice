"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type BureauStat = {
  bureau_id: number;
  bureau_code: string;
  bureau_name: string;
  total_cases: number;
  active_cases: number;
  disposed_cases: number;
  overdue_cases: number;
  disposal_rate_pct: number;
};

type RegionStat = {
  region: string;
  total: number;
  active: number;
  disposed: number;
};

type MisReportData = {
  metrics: {
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
    resolved_cross_bureau_overlaps: number;
    disposal_rate_pct: number;
  };
  bureau_breakdown: BureauStat[];
  region_breakdown: RegionStat[];
  ageing_breakdown: {
    "0_15_days": number;
    "16_30_days": number;
    "31_60_days": number;
    "over_60_days": number;
  };
};

export default function ReportsPage() {
  const [data, setData] = useState<MisReportData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<MisReportData>("/reports/mis")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <Shell wide>
      {(me: Me) => (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>AICTE MIS Analytics & Compliance Reports</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                Executive intelligence across bureaus, geographical regions, SLA compliance, and ageing distributions.
              </p>
            </div>
            <a href="/api/reports/export/cases" className="btn" style={{ textDecoration: "none", fontSize: "0.88rem" }}>
              ⬇ Export Safe CSV Report
            </a>
          </div>

          {loading || !data ? (
            <p className="muted" style={{ padding: "2rem", textAlign: "center" }}>Computing MIS metrics from authorized database records…</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {/* Executive Summary Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
                <div style={{ background: "var(--panel)", padding: "1.2rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                  <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>OVERALL DISPOSAL RATE</span>
                  <h2 style={{ fontSize: "2rem", margin: "0.2rem 0", color: "var(--sealed)" }}>{data.metrics.disposal_rate_pct}%</h2>
                  <span className="muted" style={{ fontSize: "0.78rem" }}>Formula: (Disposed / Total Registered) &times; 100</span>
                </div>

                <div style={{ background: "var(--panel)", padding: "1.2rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                  <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>OVERDUE BREACHES</span>
                  <h2 style={{ fontSize: "2rem", margin: "0.2rem 0", color: data.metrics.overdue_active > 0 ? "var(--alert)" : "var(--sealed)" }}>
                    {data.metrics.overdue_active}
                  </h2>
                  <span className="muted" style={{ fontSize: "0.78rem" }}>Active cases past effective deadline</span>
                </div>

                <div style={{ background: "var(--panel)", padding: "1.2rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-1)" }}>
                  <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>CROSS-BUREAU OVERLAPS</span>
                  <h2 style={{ fontSize: "2rem", margin: "0.2rem 0", color: "#86198f" }}>
                    {data.metrics.open_cross_bureau_overlaps} <span style={{ fontSize: "1rem", color: "var(--muted)", fontWeight: 500 }}>open ({data.metrics.resolved_cross_bureau_overlaps} resolved)</span>
                  </h2>
                  <span className="muted" style={{ fontSize: "0.78rem" }}>Concurrent cases on same institution</span>
                </div>
              </div>

              {/* Bureau-Wise Workload & Disposal Table */}
              <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.2rem", overflowX: "auto" }}>
                <h2 style={{ fontSize: "1.25rem", margin: "0 0 0.8rem 0" }}>1. Bureau-Wise Complaint Workload & Disposal Efficiency</h2>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
                  <thead>
                    <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--line-strong)", textAlign: "left" }}>
                      <th style={{ padding: "8px 12px" }}>Bureau / Cell</th>
                      <th style={{ padding: "8px 12px" }}>Total Volume</th>
                      <th style={{ padding: "8px 12px" }}>Active Cases</th>
                      <th style={{ padding: "8px 12px" }}>Disposed Cases</th>
                      <th style={{ padding: "8px 12px" }}>Overdue</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Disposal Rate (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.bureau_breakdown.map((b) => (
                      <tr key={b.bureau_id} style={{ borderBottom: "1px solid var(--line)" }}>
                        <td style={{ padding: "8px 12px", fontWeight: 700 }}>
                          <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "2px 8px", borderRadius: "6px", marginRight: "8px" }}>
                            {b.bureau_code}
                          </span>
                          {b.bureau_name}
                        </td>
                        <td style={{ padding: "8px 12px" }}>{b.total_cases}</td>
                        <td style={{ padding: "8px 12px", color: "var(--stamp)" }}>{b.active_cases}</td>
                        <td style={{ padding: "8px 12px", color: "#15803d", fontWeight: 600 }}>{b.disposed_cases}</td>
                        <td style={{ padding: "8px 12px", color: b.overdue_cases > 0 ? "var(--alert)" : "var(--muted)", fontWeight: b.overdue_cases > 0 ? 700 : 400 }}>
                          {b.overdue_cases}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 700 }}>
                          {b.disposal_rate_pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Geographical Region & Ageing Breakdown */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                {/* Region Breakdown */}
                <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.2rem" }}>
                  <h2 style={{ fontSize: "1.25rem", margin: "0 0 0.8rem 0" }}>2. Regional Case Distribution</h2>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                    <thead>
                      <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--line-strong)", textAlign: "left" }}>
                        <th style={{ padding: "6px 10px" }}>Region</th>
                        <th style={{ padding: "6px 10px" }}>Total</th>
                        <th style={{ padding: "6px 10px" }}>Active</th>
                        <th style={{ padding: "6px 10px" }}>Disposed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.region_breakdown.map((r) => (
                        <tr key={r.region} style={{ borderBottom: "1px solid var(--line)" }}>
                          <td style={{ padding: "6px 10px", fontWeight: 600 }}>{r.region}</td>
                          <td style={{ padding: "6px 10px" }}>{r.total}</td>
                          <td style={{ padding: "6px 10px", color: "var(--stamp)" }}>{r.active}</td>
                          <td style={{ padding: "6px 10px", color: "#15803d" }}>{r.disposed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Ageing Breakdown */}
                <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.2rem" }}>
                  <h2 style={{ fontSize: "1.25rem", margin: "0 0 0.8rem 0" }}>3. Active Case Ageing Analysis</h2>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", marginTop: "1rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0.8rem", background: "#f0fdf4", borderRadius: "var(--r-sm)" }}>
                      <span>0 &ndash; 15 Calendar Days</span>
                      <strong style={{ color: "#166534" }}>{data.ageing_breakdown["0_15_days"]} cases</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0.8rem", background: "#fefce8", borderRadius: "var(--r-sm)" }}>
                      <span>16 &ndash; 30 Calendar Days</span>
                      <strong style={{ color: "#854d0e" }}>{data.ageing_breakdown["16_30_days"]} cases</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0.8rem", background: "#fff7ed", borderRadius: "var(--r-sm)" }}>
                      <span>31 &ndash; 60 Calendar Days</span>
                      <strong style={{ color: "#c2410c" }}>{data.ageing_breakdown["31_60_days"]} cases</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0.8rem", background: "#fef2f2", borderRadius: "var(--r-sm)" }}>
                      <span>Over 60 Calendar Days</span>
                      <strong style={{ color: "#991b1b" }}>{data.ageing_breakdown["over_60_days"]} cases</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
