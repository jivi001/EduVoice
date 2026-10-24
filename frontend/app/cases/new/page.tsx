"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Shell from "@/components/Shell";
import { api, Me } from "@/lib/api";

export default function RegisterCasePage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [permId, setPermId] = useState("");
  const [bureauId, setBureauId] = useState("2"); // Default PGRC
  const [complainantType, setComplainantType] = useState("Student");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [category, setCategory] = useState("Capitation Fee");
  const [confidentiality, setConfidentiality] = useState("ORDINARY");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const res = await api<{ id: number; case_id: string }>("/cases", {
        method: "POST",
        body: {
          permanent_id: permId.trim(),
          bureau_id: Number(bureauId),
          complainant_type: complainantType,
          complainant_name: name.trim() || null,
          complainant_email: email.trim() || null,
          complainant_phone: phone.trim() || null,
          category,
          confidentiality_level: confidentiality,
          subject: subject.trim(),
          description: description.trim(),
        },
      });

      router.push(`/cases/${res.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to register case.");
      setBusy(false);
    }
  }

  return (
    <Shell wide={false}>
      {(me: Me) => (
        <div style={{ maxWidth: "700px", margin: "0 auto" }}>
          <div style={{ marginBottom: "1.2rem" }}>
            <button className="link" onClick={() => router.back()} style={{ fontSize: "0.85rem" }}>
              &larr; Back to Dashboard
            </button>
            <h1 style={{ fontSize: "1.8rem", margin: "0.4rem 0 0.2rem 0" }}>Register Institution Complaint</h1>
            <p className="muted" style={{ margin: 0, fontSize: "0.92rem" }}>
              Allocates an authoritative AICTE tracking ID, configures SLA deadline, and runs cross-bureau overlap detection.
            </p>
          </div>

          {error && (
            <div style={{ padding: "0.8rem 1rem", borderRadius: "var(--r-sm)", marginBottom: "1rem", background: "var(--alert-soft)", color: "var(--alert)", fontWeight: 600 }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ background: "var(--panel)", padding: "1.8rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label>AICTE Permanent ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 1-10928374"
                  value={permId}
                  onChange={(e) => setPermId(e.target.value)}
                />
                <span className="muted" style={{ fontSize: "0.75rem" }}>Demo IDs: 1-10928374, 1-20938475, 1-30948576</span>
              </div>

              <div>
                <label>Responsible AICTE Bureau *</label>
                <select value={bureauId} onChange={(e) => setBureauId(e.target.value)}>
                  <option value="2">Public Grievance Redressal Cell (PGRC)</option>
                  <option value="1">Regulation Bureau (RB)</option>
                  <option value="3">Approval Bureau (AB)</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label>Complaint Source Type</label>
                <select value={complainantType} onChange={(e) => setComplainantType(e.target.value)}>
                  <option value="Student">Student</option>
                  <option value="Faculty">Faculty</option>
                  <option value="Other Stakeholder">Other Stakeholder / Parent</option>
                </select>
              </div>

              <div>
                <label>Confidentiality Level</label>
                <select value={confidentiality} onChange={(e) => setConfidentiality(e.target.value)}>
                  <option value="ORDINARY">Ordinary (Shared Metadata across Bureaus)</option>
                  <option value="HIGH">High (Masked / Exclusive to Responsible Bureau)</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.8rem" }}>
              <div>
                <label>Complainant Name</label>
                <input type="text" placeholder="Full Name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <label>Email Address</label>
                <input type="email" placeholder="email@domain.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <label>Contact Phone</label>
                <input type="text" placeholder="+91..." value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1rem" }}>
              <div>
                <label>Category *</label>
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="Capitation Fee">Capitation Fee</option>
                  <option value="Fee Refund">Fee Refund</option>
                  <option value="Ragging">Ragging</option>
                  <option value="Infrastructure Deficiency">Infrastructure Deficiency</option>
                  <option value="Faculty Harassment">Faculty Harassment</option>
                  <option value="Admission Irregularity">Admission Irregularity</option>
                  <option value="General Grievance">General Grievance</option>
                </select>
              </div>

              <div>
                <label>Grievance Subject *</label>
                <input
                  type="text"
                  required
                  placeholder="Summary of grievance..."
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label>Detailed Description & Facts *</label>
              <textarea
                rows={5}
                required
                placeholder="Comprehensive description of the complaint or incident..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.8rem", marginTop: "0.5rem" }}>
              <button type="button" className="btn quiet" onClick={() => router.back()}>
                Cancel
              </button>
              <button type="submit" className="btn" disabled={busy}>
                {busy ? "Registering & Running Checks…" : "Register Case"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Shell>
  );
}
