"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, homeFor, Me } from "@/lib/api";
import { Mark } from "@/components/Mark";

type NotificationItem = {
  id: number;
  alert_type: string;
  title: string;
  message: string;
  status: string;
  related_case_id?: number;
  related_case_number?: string;
  created_at: string;
};

export default function Shell({
  role,
  wide = true,
  children,
}: {
  role?: string;
  wide?: boolean;
  children: (me: Me) => React.ReactNode;
}) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [notifs, setNotifs] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const [simDate, setSimDate] = useState<string>("");

  const loadData = () => {
    api<Me>("/auth/me")
      .then((m) => {
        if (m.must_change_password && typeof window !== "undefined" && window.location.pathname !== "/account") {
          router.replace("/account?required=1");
          return;
        }
        if (!role || m.role === role || (role === "admin" && m.role === "admin")) {
          setMe(m);
        } else if (role && m.role !== role && role !== "any") {
          router.replace(homeFor(m.role));
        } else {
          setMe(m);
        }
      })
      .catch((e) => e instanceof ApiError && router.replace("/"));

    api<{ unread_count: number; notifications: NotificationItem[] }>("/notifications")
      .then((res) => {
        setUnreadCount(res.unread_count);
        setNotifs(res.notifications);
      })
      .catch(() => {});

    api<{ current_date: string }>("/clock")
      .then((c) => setSimDate(c.current_date))
      .catch(() => {});
  };

  useEffect(() => {
    loadData();
    // Poll every 12 seconds when window is active
    const timer = setInterval(() => {
      if (typeof document !== "undefined" && !document.hidden) {
        api<{ unread_count: number; notifications: NotificationItem[] }>("/notifications")
          .then((res) => {
            setUnreadCount(res.unread_count);
            setNotifs(res.notifications);
          })
          .catch(() => {});
      }
    }, 12000);
    return () => clearInterval(timer);
  }, [role, router]);

  async function signOut() {
    await api("/auth/logout", { method: "POST", body: {} });
    router.replace("/");
  }

  async function ackNotification(id: number) {
    await api(`/notifications/${id}/acknowledge`, { method: "POST" });
    loadData();
  }

  async function ackAll() {
    await api("/notifications/acknowledge-all", { method: "POST" });
    loadData();
  }

  async function advanceClock(days: number) {
    await api("/clock/advance", { method: "POST", body: { days, hours: 0 } });
    loadData();
  }

  async function resetClock() {
    await api("/clock/reset", { method: "POST" });
    loadData();
  }

  if (!me) {
    return (
      <>
        <header className="bar">
          <a className="brand" href="/"><Mark size={24} /> EduVoice</a>
        </header>
        <main className="page"><p className="muted">Loading workspace…</p></main>
      </>
    );
  }

  const roleLabel =
    me.role === "admin"
      ? "Central Admin"
      : me.role === "supervisor"
      ? "Bureau Supervisor"
      : me.role === "officer"
      ? `Bureau Officer (${me.bureaus?.map((b) => b.code).join(", ") || "General"})`
      : me.role === "auditor"
      ? "Auditor"
      : me.role;

  return (
    <>
      <header className="bar" style={{ padding: "0.8rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1.2rem" }}>
          <a className="brand" href="/dashboard" style={{ textDecoration: "none" }}>
            <Mark size={24} />
            <span style={{ fontWeight: 700, letterSpacing: "-0.02em" }}>EduVoice</span>
            <span style={{ fontSize: "0.75rem", background: "var(--stamp-soft)", color: "var(--stamp-deep)", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>
              SIH26264
            </span>
          </a>

          <nav style={{ display: "flex", gap: "0.8rem", marginLeft: "1rem", fontSize: "0.92rem", fontWeight: 500 }}>
            <a href="/dashboard" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>Dashboard</a>
            <a href="/institutions" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>Institutions</a>
            <a href="/cases/new" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>+ New Case</a>
            <a href="/import" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>CSV Ingest</a>
            <a href="/overlaps" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>Overlaps</a>
            <a href="/reports" style={{ textDecoration: "none", color: "var(--ink)", padding: "4px 8px" }}>MIS Reports</a>
          </nav>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1.2rem" }}>
          {/* Time Machine Widget */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", background: "var(--paper)", border: "1px solid var(--line-strong)", borderRadius: "20px", padding: "3px 10px", fontSize: "0.82rem" }}>
            <span style={{ fontWeight: 600 }}>📅 {simDate || "Live"}</span>
            <button className="link" onClick={() => advanceClock(10)} title="Advance clock by 10 days" style={{ fontSize: "0.78rem" }}>+10d</button>
            <button className="link" onClick={() => advanceClock(30)} title="Advance clock by 30 days" style={{ fontSize: "0.78rem" }}>+30d</button>
            <button className="link" onClick={resetClock} title="Reset clock" style={{ fontSize: "0.78rem", color: "var(--alert)" }}>Reset</button>
          </div>

          {/* Notifications Popover */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              style={{
                background: "none",
                border: "1px solid var(--line-strong)",
                borderRadius: "50%",
                width: "36px",
                height: "36px",
                cursor: "pointer",
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              title="Notifications"
            >
              🔔
              {unreadCount > 0 && (
                <span
                  style={{
                    position: "absolute",
                    top: "-4px",
                    right: "-4px",
                    background: "var(--alert)",
                    color: "white",
                    borderRadius: "10px",
                    fontSize: "0.7rem",
                    padding: "1px 5px",
                    fontWeight: 700,
                  }}
                >
                  {unreadCount}
                </span>
              )}
            </button>

            {showNotifs && (
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  top: "42px",
                  width: "360px",
                  maxHeight: "420px",
                  overflowY: "auto",
                  background: "var(--panel)",
                  border: "1px solid var(--line-strong)",
                  borderRadius: "var(--r-md)",
                  boxShadow: "var(--shadow-2)",
                  padding: "0.8rem",
                  zIndex: 100,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)", paddingBottom: "0.5rem", marginBottom: "0.5rem" }}>
                  <strong style={{ fontSize: "0.95rem" }}>Notifications ({unreadCount} unread)</strong>
                  {unreadCount > 0 && (
                    <button className="link" onClick={ackAll} style={{ fontSize: "0.8rem" }}>
                      Mark all read
                    </button>
                  )}
                </div>

                {!notifs.length ? (
                  <p className="muted" style={{ margin: "1rem 0", textAlign: "center", fontSize: "0.85rem" }}>
                    No notifications right now.
                  </p>
                ) : (
                  notifs.slice(0, 15).map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: "0.5rem",
                        borderRadius: "var(--r-sm)",
                        background: n.status === "UNREAD" ? "var(--stamp-wash)" : "transparent",
                        marginBottom: "0.4rem",
                        fontSize: "0.85rem",
                        borderBottom: "1px solid var(--line)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <span style={{ fontWeight: 600, color: "var(--ink)" }}>{n.title}</span>
                        {n.status === "UNREAD" && (
                          <button
                            className="link"
                            onClick={() => ackNotification(n.id)}
                            style={{ fontSize: "0.75rem", color: "var(--stamp)" }}
                          >
                            Dismiss
                          </button>
                        )}
                      </div>
                      <p style={{ margin: "0.2rem 0", color: "var(--ink-soft)", fontSize: "0.82rem" }}>{n.message}</p>
                      <span className="muted" style={{ fontSize: "0.72rem" }}>
                        {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", fontSize: "0.82rem" }}>
            <span style={{ fontWeight: 600, color: "var(--ink)" }}>{me.name}</span>
            <span style={{ color: "var(--stamp-deep)", fontWeight: 500 }}>{roleLabel}</span>
          </div>

          <button className="btn quiet" onClick={signOut} style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}>
            Sign out
          </button>
        </div>
      </header>
      <main className={wide ? "page wide" : "page"} style={{ maxWidth: wide ? "1240px" : "800px" }}>
        {children(me)}
      </main>
    </>
  );
}
