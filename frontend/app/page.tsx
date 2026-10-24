"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, homeFor, Me } from "@/lib/api";
import { Mark } from "@/components/Mark";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const googlePending = params.get("google_pending") === "1";
  const googleError = params.get("google_error");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Check if already signed in
  useEffect(() => {
    api<Me>("/auth/me")
      .then((m) => {
        router.push(homeFor(m.role));
      })
      .catch(() => {});
  }, [router]);

  async function performLogin(user: string, pass: string) {
    setError("");
    setBusy(true);
    try {
      const me = await api<Me>("/auth/login", {
        body: { username: user, password: pass },
      });
      router.push(homeFor(me.role));
    } catch (err: any) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setBusy(false);
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    performLogin(username, password);
  }

  return (
    <div className="login" style={{ maxWidth: "1000px", margin: "3rem auto" }}>
      <section>
        <div className="hero-mark"><Mark size={48} /></div>
        <h1 style={{ fontSize: "2.4rem", fontWeight: 700, lineHeight: 1.15 }}>
          EduVoice: Integrated Complaint Dashboard
        </h1>
        <p className="lede" style={{ fontSize: "1.05rem", color: "var(--ink-soft)", margin: "0.8rem 0 1.5rem" }}>
          Smart India Hackathon <strong>SIH26264</strong> &bull; Unified cross-bureau tracking and automated overlap detection across Regulation Bureau (RB), Public Grievance Redressal Cell (PGRC), and Approval Bureau (AB).
        </p>

        <div style={{ background: "var(--paper-raised)", padding: "1.2rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)", marginBottom: "1.5rem" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem", textTransform: "uppercase", color: "var(--stamp-deep)", letterSpacing: "0.03em" }}>
            Key Smart Automation Capabilities:
          </h3>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.88rem", lineHeight: 1.6, color: "var(--ink)" }}>
            <li><strong>Single-Window Dashboard:</strong> Real-time consolidated view of technical institutions.</li>
            <li><strong>Deterministic Overlap Detection:</strong> Flags concurrent cases on same college across divisions.</li>
            <li><strong>Strict 5-Stage Lifecycle:</strong> Pending &rarr; Under Process &rarr; Transferred / Escalated &rarr; Disposed.</li>
            <li><strong>Cross-Bureau Confidentiality:</strong> High-confidentiality complaints masked from other bureaus.</li>
            <li><strong>Configurable SLA & Ageing:</strong> Deterministic countdowns with formula-safe MIS CSV exports.</li>
          </ul>
        </div>
      </section>

      <form className="card login-card" onSubmit={onSubmit} style={{ background: "white", padding: "1.8rem", borderRadius: "var(--r-md)", border: "1px solid var(--line-strong)" }}>
        <h2 style={{ fontSize: "1.4rem", margin: "0 0 0.4rem 0" }}>Sign In to Portal</h2>
        <p className="muted" style={{ fontSize: "0.85rem", margin: "0 0 1rem 0" }}>Select a pre-configured role below or enter credentials.</p>

        {googlePending && <p className="msg ok">Your account is verified and waiting for administrator approval.</p>}
        {googleError && <p className="msg error">{googleError}</p>}
        {error && <p className="msg error">{error}</p>}

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            type="text"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button className="btn big" style={{ width: "100%", justifyContent: "center", marginTop: "0.5rem" }} disabled={busy}>
          {busy ? "Signing in…" : "Sign In"}
        </button>

        {/* 1-Click Demo Logins for Evaluators */}
        <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
          <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 700, textTransform: "uppercase", display: "block", marginBottom: "0.6rem" }}>
            1-Click Demo Accounts (SIH Evaluators):
          </span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("admin"); setPassword("admin123"); performLogin("admin", "admin123"); }}
            >
              👑 Central Admin
            </button>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("officer_pgrc"); setPassword("officer123"); performLogin("officer_pgrc", "officer123"); }}
            >
              📋 PGRC Officer
            </button>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("officer_rb"); setPassword("officer123"); performLogin("officer_rb", "officer123"); }}
            >
              ⚖️ RB Officer
            </button>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("officer_ab"); setPassword("officer123"); performLogin("officer_ab", "officer123"); }}
            >
              🏢 AB Officer
            </button>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("supervisor_rb"); setPassword("super123"); performLogin("supervisor_rb", "super123"); }}
            >
              🛡️ RB Supervisor
            </button>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: "0.78rem", padding: "0.4rem", justifyContent: "center" }}
              onClick={() => { setUsername("auditor"); setPassword("auditor123"); performLogin("auditor", "auditor123"); }}
            >
              🔍 Auditor
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default function Login() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
