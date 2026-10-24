"use client";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

type InstItem = {
  id: number;
  permanent_id: string;
  name: string;
  state: string;
  region: string;
  address: string | null;
  created_at: string;
};

type InstProfile = {
  id: number;
  permanent_id: string;
  name: string;
  state: string;
  region: string;
  address: string | null;
  total_cases: number;
  bureau_breakdown: Record<string, number>;
  cases: Array<{
    id: number;
    case_id: string;
    current_bureau_code: string;
    category: string;
    subject: string;
    status: string;
    received_date: string | null;
    sla_status: string;
  }>;
};

export default function InstitutionsPage() {
  const [institutions, setInstitutions] = useState<InstItem[]>([]);
  const [search, setSearch] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [selectedProfile, setSelectedProfile] = useState<InstProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  // Add Institution Form
  const [newPid, setNewPid] = useState("");
  const [newName, setNewName] = useState("");
  const [newState, setNewState] = useState("");
  const [newRegion, setNewRegion] = useState("Northern");
  const [newAddr, setNewAddr] = useState("");
  const [formErr, setFormErr] = useState<string | null>(null);

  const loadInstitutions = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search.trim()) params.append("q", search.trim());
    if (regionFilter) params.append("region", regionFilter);

    api<InstItem[]>(`/institutions?${params.toString()}`)
      .then(setInstitutions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, regionFilter]);

  useEffect(() => {
    loadInstitutions();
  }, [loadInstitutions]);

  function viewProfile(id: number) {
    api<InstProfile>(`/institutions/${id}`)
      .then(setSelectedProfile)
      .catch(() => {});
  }

  async function handleAddInstitution(e: React.FormEvent) {
    e.preventDefault();
    setFormErr(null);
    try {
      await api("/institutions", {
        method: "POST",
        body: { permanent_id: newPid.trim(), name: newName.trim(), state: newState.trim(), region: newRegion, address: newAddr.trim() || null },
      });
      setShowAddModal(false);
      setNewPid("");
      setNewName("");
      setNewState("");
      setNewAddr("");
      loadInstitutions();
    } catch (err: any) {
      setFormErr(err.message || "Failed to create institution.");
    }
  }

  return (
    <Shell wide>
      {(me: Me) => (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", margin: 0, fontWeight: 700 }}>AICTE Institution Registry</h1>
              <p className="muted" style={{ margin: "0.2rem 0 0 0", fontSize: "0.95rem" }}>
                Authoritative registry of technical education institutions. View 360-degree multi-bureau grievance histories.
              </p>
            </div>
            {me.role === "admin" && (
              <button className="btn" onClick={() => setShowAddModal(true)}>
                + Register Institution
              </button>
            )}
          </div>

          {/* Filter Bar */}
          <div style={{ background: "var(--panel)", padding: "1rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", marginBottom: "1.2rem", display: "flex", gap: "1rem" }}>
            <input
              type="text"
              placeholder="Search by Permanent ID or Name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: 1 }}
            />
            <select value={regionFilter} onChange={(e) => setRegionFilter(e.target.value)} style={{ width: "200px" }}>
              <option value="">All Regions</option>
              <option value="Northern">Northern</option>
              <option value="Western">Western</option>
              <option value="Southern">Southern</option>
              <option value="Eastern">Eastern</option>
              <option value="South-West">South-West</option>
              <option value="North-West">North-West</option>
              <option value="Central">Central</option>
            </select>
            <button className="btn quiet" onClick={loadInstitutions}>
              Search
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: selectedProfile ? "1fr 1fr" : "1fr", gap: "1.5rem" }}>
            {/* Institution Table */}
            <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", overflowX: "auto" }}>
              {loading ? (
                <p className="muted" style={{ padding: "2rem", textAlign: "center" }}>Loading institutions…</p>
              ) : !institutions.length ? (
                <p className="muted" style={{ padding: "2rem", textAlign: "center" }}>No institutions found.</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
                  <thead>
                    <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--line-strong)", textAlign: "left" }}>
                      <th style={{ padding: "0.75rem 1rem" }}>Permanent ID</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Institution Name</th>
                      <th style={{ padding: "0.75rem 1rem" }}>Region / State</th>
                      <th style={{ padding: "0.75rem 1rem", textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {institutions.map((inst) => (
                      <tr key={inst.id} style={{ borderBottom: "1px solid var(--line)" }}>
                        <td style={{ padding: "0.75rem 1rem", fontWeight: 700 }}>
                          <code>{inst.permanent_id}</code>
                        </td>
                        <td style={{ padding: "0.75rem 1rem", fontWeight: 600 }}>{inst.name}</td>
                        <td style={{ padding: "0.75rem 1rem" }}>
                          {inst.region} <span className="muted">({inst.state})</span>
                        </td>
                        <td style={{ padding: "0.75rem 1rem", textAlign: "right" }}>
                          <button className="btn quiet" onClick={() => viewProfile(inst.id)} style={{ padding: "0.3rem 0.7rem", fontSize: "0.8rem" }}>
                            360° Profile &rarr;
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* 360-Degree Profile Side-Panel */}
            {selectedProfile && (
              <div style={{ background: "var(--panel)", borderRadius: "var(--r-md)", border: "2px solid var(--stamp)", padding: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--line)", paddingBottom: "0.8rem", marginBottom: "1rem" }}>
                  <div>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>360° Multi-Bureau Case Profile</span>
                    <h2 style={{ fontSize: "1.4rem", margin: "0.2rem 0" }}>{selectedProfile.name}</h2>
                    <div style={{ fontSize: "0.85rem" }}>
                      Permanent ID: <code>{selectedProfile.permanent_id}</code> &bull; {selectedProfile.region} ({selectedProfile.state})
                    </div>
                  </div>
                  <button className="link" onClick={() => setSelectedProfile(null)} style={{ fontSize: "1.2rem" }}>
                    &times;
                  </button>
                </div>

                <div style={{ display: "flex", gap: "0.6rem", marginBottom: "1.2rem", flexWrap: "wrap" }}>
                  <div style={{ background: "var(--paper)", padding: "0.5rem 0.8rem", borderRadius: "var(--r-sm)" }}>
                    <span className="muted" style={{ fontSize: "0.75rem" }}>Total Grievances:</span>
                    <strong style={{ display: "block", fontSize: "1.2rem" }}>{selectedProfile.total_cases}</strong>
                  </div>
                  {Object.entries(selectedProfile.bureau_breakdown).map(([bcode, cnt]) => (
                    <div key={bcode} style={{ background: "var(--stamp-wash)", padding: "0.5rem 0.8rem", borderRadius: "var(--r-sm)" }}>
                      <span className="muted" style={{ fontSize: "0.75rem" }}>Bureau {bcode}:</span>
                      <strong style={{ display: "block", fontSize: "1.2rem", color: "var(--stamp-deep)" }}>{cnt}</strong>
                    </div>
                  ))}
                </div>

                <h3 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem 0" }}>Cross-Bureau Case History</h3>
                {!selectedProfile.cases.length ? (
                  <p className="muted" style={{ fontSize: "0.85rem" }}>No grievances registered across any division.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", maxHeight: "350px", overflowY: "auto" }}>
                    {selectedProfile.cases.map((c) => (
                      <div key={c.id} style={{ border: "1px solid var(--line)", borderRadius: "var(--r-sm)", padding: "0.6rem 0.8rem", fontSize: "0.85rem", background: "white" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                          <a href={`/cases/${c.id}`} style={{ fontWeight: 700, color: "var(--stamp)", textDecoration: "none" }}>
                            {c.case_id}
                          </a>
                          <span style={{ background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "1px 6px", borderRadius: "8px", fontSize: "0.75rem", fontWeight: 700 }}>
                            {c.current_bureau_code}
                          </span>
                        </div>
                        <div style={{ fontWeight: 600 }}>{c.category}: {c.subject}</div>
                        <div className="muted" style={{ fontSize: "0.78rem", marginTop: "0.2rem" }}>
                          Status: {c.status} &bull; Received: {c.received_date || "N/A"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Add Institution Modal */}
          {showAddModal && (
            <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "1rem" }}>
              <form onSubmit={handleAddInstitution} style={{ background: "white", padding: "1.5rem", borderRadius: "var(--r-md)", width: "100%", maxWidth: "500px", boxShadow: "var(--shadow-2)" }}>
                <h2 style={{ margin: "0 0 1rem 0" }}>Register Institution in Master Registry</h2>
                {formErr && <p style={{ color: "var(--alert)", fontSize: "0.85rem" }}>{formErr}</p>}
                <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                  <div>
                    <label>AICTE Permanent ID *</label>
                    <input type="text" required placeholder="e.g. 1-90817263" value={newPid} onChange={(e) => setNewPid(e.target.value)} />
                  </div>
                  <div>
                    <label>Official Institution Name *</label>
                    <input type="text" required placeholder="Full registered college name" value={newName} onChange={(e) => setNewName(e.target.value)} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.8rem" }}>
                    <div>
                      <label>State *</label>
                      <input type="text" required placeholder="e.g. Karnataka" value={newState} onChange={(e) => setNewState(e.target.value)} />
                    </div>
                    <div>
                      <label>Region *</label>
                      <select value={newRegion} onChange={(e) => setNewRegion(e.target.value)}>
                        <option value="Northern">Northern</option>
                        <option value="Western">Western</option>
                        <option value="Southern">Southern</option>
                        <option value="Eastern">Eastern</option>
                        <option value="South-West">South-West</option>
                        <option value="North-West">North-West</option>
                        <option value="Central">Central</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label>Address</label>
                    <textarea rows={2} placeholder="Campus location..." value={newAddr} onChange={(e) => setNewAddr(e.target.value)} />
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", marginTop: "1rem" }}>
                  <button type="button" className="btn quiet" onClick={() => setShowAddModal(false)}>Cancel</button>
                  <button type="submit" className="btn">Save Institution</button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
