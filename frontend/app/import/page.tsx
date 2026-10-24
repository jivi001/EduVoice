"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type RowReport = {
  row_number: number;
  permanent_id: string;
  source_record_id: string | null;
  status: string;
  errors: string[];
  created_case_id: number | null;
};

type ImportResult = {
  batch_id: number | null;
  filename: string;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  review_rows: number;
  status: string;
  rows: RowReport[];
};

type IssueItem = {
  id: number;
  batch_id: number;
  row_id: number;
  issue_type: string;
  description: string;
  status: string;
};

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [issues, setIssues] = useState<IssueItem[]>([]);

  const loadIssues = useCallback(() => {
    api<IssueItem[]>("/import/issues?status=PENDING")
      .then(setIssues)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setBusy(true);
    setErrorMsg(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("dry_run", String(dryRun));

    try {
      const res = await fetch("/api/import/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Upload failed.");
      }

      const report: ImportResult = await res.json();
      setResult(report);
      loadIssues();
    } catch (err: any) {
      setErrorMsg(err.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resolveIssue(id: number, action: "RESOLVE" | "IGNORE") {
    await api(`/import/issues/${id}/resolve`, {
      method: "POST",
      body: { action, notes: "Processed via administrator dashboard" },
    });
    loadIssues();
  }

  const sampleCsv = `permanent_id,institution_name,bureau_code,source_system,source_record_id,category,subject,description,received_date,confidentiality_level,status,due_date
1-10928374,Apex Institute of Technology,PGRC,STATE_PORTAL,GRV-2026-901,Capitation Fee,Illegal admission fee,Demand for 50000 building fund,2026-03-01,ORDINARY,Pending,2026-03-31
1-20938475,Western College of Engineering & Tech,RB,STATE_PORTAL,GRV-2026-902,Infrastructure Deficiency,Inadequate computing facilities,Computer center servers non-operational,2026-03-02,HIGH,Under Process,2026-04-01
`;

  function downloadSample() {
    const blob = new Blob([sampleCsv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "aicte_complaints_sample_template.csv";
    a.click();
  }

  return (
    <Shell wide>
      {(me: Me) => (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>CSV Grievance Ingestion & Sync</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                Ingest batches (max 200 rows) with strict registry verification, external record idempotency, and synchronous overlap alerts.
              </p>
            </div>
            <button className="btn quiet" onClick={downloadSample} style={{ fontSize: "0.88rem" }}>
              ⬇ Download Sample CSV Template
            </button>
          </div>

          {errorMsg && (
            <div style={{ padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", marginBottom: "1rem", background: "var(--alert-soft)", color: "var(--alert)", fontWeight: 600 }}>
              {errorMsg}
            </div>
          )}

          {/* Upload Card */}
          <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.5rem", marginBottom: "1.5rem" }}>
            <form onSubmit={handleUpload}>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                <input
                  type="file"
                  accept=".csv"
                  required
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  style={{ flex: "1 1 300px" }}
                />

                <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", margin: 0, cursor: "pointer", fontSize: "0.9rem" }}>
                  <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
                  Dry-run Preview (No database commits)
                </label>

                <button type="submit" className="btn" disabled={!file || busy}>
                  {busy ? "Validating & Processing…" : "Upload & Ingest"}
                </button>
              </div>
              <p className="muted" style={{ margin: "0.6rem 0 0 0", fontSize: "0.8rem" }}>
                Limit: Maximum 200 data rows per batch. Existing (source_system, source_record_id) records are never overwritten.
              </p>
            </form>
          </div>

          {/* Processing Outcome Summary */}
          {result && (
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.5rem", marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)", paddingBottom: "0.8rem", marginBottom: "1rem" }}>
                <div>
                  <h2 style={{ fontSize: "1.3rem", margin: 0 }}>Batch Ingestion Report: {result.filename}</h2>
                  <span className="muted" style={{ fontSize: "0.85rem" }}>
                    Status: <strong style={{ color: result.status === "COMPLETED" ? "#15803d" : "#b45309" }}>{result.status}</strong>
                  </span>
                </div>
                {result.batch_id && (
                  <a href={`/api/import/batches/${result.batch_id}/report`} className="btn quiet" style={{ fontSize: "0.82rem", textDecoration: "none" }}>
                    ⬇ Download Audit Report (CSV)
                  </a>
                )}
              </div>

              <div style={{ display: "flex", gap: "1rem", marginBottom: "1.2rem", flexWrap: "wrap" }}>
                <div style={{ background: "var(--paper)", padding: "0.6rem 1rem", borderRadius: "var(--r-sm)" }}>
                  <span className="muted" style={{ fontSize: "0.75rem" }}>Total Rows:</span>
                  <strong style={{ display: "block", fontSize: "1.3rem" }}>{result.total_rows}</strong>
                </div>
                <div style={{ background: "#dcfce7", padding: "0.6rem 1rem", borderRadius: "var(--r-sm)", border: "1px solid #86efac" }}>
                  <span style={{ fontSize: "0.75rem", color: "#166534" }}>Accepted & Committed:</span>
                  <strong style={{ display: "block", fontSize: "1.3rem", color: "#166534" }}>{result.accepted_rows}</strong>
                </div>
                <div style={{ background: "#fef3c7", padding: "0.6rem 1rem", borderRadius: "var(--r-sm)", border: "1px solid #fde047" }}>
                  <span style={{ fontSize: "0.75rem", color: "#854d0e" }}>Held for Review:</span>
                  <strong style={{ display: "block", fontSize: "1.3rem", color: "#854d0e" }}>{result.review_rows}</strong>
                </div>
                <div style={{ background: "#fee2e2", padding: "0.6rem 1rem", borderRadius: "var(--r-sm)", border: "1px solid #fca5a5" }}>
                  <span style={{ fontSize: "0.75rem", color: "#991b1b" }}>Rejected (Invalid):</span>
                  <strong style={{ display: "block", fontSize: "1.3rem", color: "#991b1b" }}>{result.rejected_rows}</strong>
                </div>
              </div>

              {/* Row Outcomes Table */}
              <h3 style={{ fontSize: "1rem", margin: "0 0 0.6rem 0" }}>Row-Level Validation & Execution Logs</h3>
              <div style={{ maxHeight: "300px", overflowY: "auto", border: "1px solid var(--line)", borderRadius: "var(--r-sm)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ background: "var(--paper)", textAlign: "left" }}>
                      <th style={{ padding: "6px 10px" }}>Row</th>
                      <th style={{ padding: "6px 10px" }}>Permanent ID</th>
                      <th style={{ padding: "6px 10px" }}>Source Record ID</th>
                      <th style={{ padding: "6px 10px" }}>Status</th>
                      <th style={{ padding: "6px 10px" }}>Validation Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r) => (
                      <tr key={r.row_number} style={{ borderBottom: "1px solid var(--line)" }}>
                        <td style={{ padding: "6px 10px", fontWeight: 700 }}>#{r.row_number}</td>
                        <td style={{ padding: "6px 10px" }}><code>{r.permanent_id || "N/A"}</code></td>
                        <td style={{ padding: "6px 10px" }}>{r.source_record_id || "N/A"}</td>
                        <td style={{ padding: "6px 10px" }}>
                          {r.status === "ACCEPTED" && <span style={{ color: "#166534", fontWeight: 700 }}>ACCEPTED</span>}
                          {r.status === "NEEDS_REVIEW" && <span style={{ color: "#b45309", fontWeight: 700 }}>REVIEW QUEUE</span>}
                          {r.status === "REJECTED" && <span style={{ color: "#b91c1c", fontWeight: 700 }}>REJECTED</span>}
                        </td>
                        <td style={{ padding: "6px 10px", color: "var(--ink-soft)" }}>
                          {r.errors?.join("; ") || "Successfully created and linked."}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Import Issues Review Queue */}
          <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
              <h2 style={{ fontSize: "1.3rem", margin: 0 }}>Import Review Queue ({issues.length} pending items)</h2>
              <button className="btn quiet" onClick={loadIssues} style={{ fontSize: "0.8rem" }}>Refresh Queue</button>
            </div>
            <p className="muted" style={{ margin: "0 0 1rem 0", fontSize: "0.85rem" }}>
              Registry mismatches, unknown institution permanent IDs, and duplicate source submissions flagged for authorized human review.
            </p>

            {!issues.length ? (
              <p className="muted" style={{ textAlign: "center", padding: "1.5rem" }}>No unresolved import issues in queue.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                {issues.map((iss) => (
                  <div key={iss.id} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "0.8rem 1rem", background: "var(--paper-raised)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ background: "#fef3c7", color: "#b45309", padding: "2px 6px", borderRadius: "6px", fontSize: "0.75rem", fontWeight: 700 }}>
                        {iss.issue_type}
                      </span>
                      <p style={{ margin: "0.3rem 0 0 0", fontSize: "0.88rem", color: "var(--ink)" }}>{iss.description}</p>
                    </div>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button className="btn quiet" onClick={() => resolveIssue(iss.id, "RESOLVE")} style={{ fontSize: "0.8rem", padding: "0.3rem 0.6rem" }}>
                        Resolve
                      </button>
                      <button className="btn quiet" onClick={() => resolveIssue(iss.id, "IGNORE")} style={{ fontSize: "0.8rem", padding: "0.3rem 0.6rem", color: "var(--muted)" }}>
                        Dismiss
                      </button>
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
