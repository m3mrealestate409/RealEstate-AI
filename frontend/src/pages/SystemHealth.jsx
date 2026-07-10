import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function SystemHealth() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  function load() {
    api.systemHealth().then(setD).catch((e) => setErr(e.message));
  }
  useEffect(() => { load(); }, []);

  if (err) return <div className="page"><div className="alert alert-error">{err}</div></div>;
  if (!d) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <div className="page-head row-between">
        <div>
          <h2>System Health</h2>
          <p className="muted">Live status of the engine's services.</p>
        </div>
        <button className="btn" onClick={load}>Refresh</button>
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
    </div>
  );
}
