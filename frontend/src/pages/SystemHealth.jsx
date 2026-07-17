import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Lives inside Admin → System rather than in the sidebar: it answers "is the
// engine up", which you look at when something is wrong, not every day.
export function SystemHealthPanel() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  function load() {
    api.systemHealth().then(setD).catch((e) => setErr(e.message));
  }
  useEffect(() => { load(); }, []);

  if (err) return <div className="alert alert-error">{err}</div>;
  if (!d) return <div className="muted">Loading…</div>;

  return (
    <div className="admin-form">
      <div className="settings-note">
        <b>🩺 Live status of the engine's services.</b> If the assistant is behaving oddly, look here
        first — a service being down explains more than any prompt ever will.
      </div>

      <div className={`health-banner ${d.healthy ? "ok" : "bad"}`}>
        {d.healthy ? "✓ All systems operational" : "✗ One or more services are down"}
      </div>

      <div className="health-list">
        {d.checks.map((c, i) => (
          <div className="health-row" key={i}>
            <span className={`health-dot ${c.ok ? "on" : "off"}`} />
            <span className="health-name">{c.name}</span>
            <span className="health-detail muted">{c.detail}</span>
            <span className={`status-chip ${c.ok ? "chip-green" : "chip-red"}`}>{c.ok ? "up" : "down"}</span>
          </div>
        ))}
      </div>

      <button className="btn" style={{ marginTop: 14 }} onClick={load}>Refresh</button>
    </div>
  );
}
