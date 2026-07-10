import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// RAG pipeline monitoring — confirms brochures actually got indexed.
export default function Knowledge() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.knowledgeOverview().then(setD).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="page"><div className="alert alert-error">{err}</div></div>;
  if (!d) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Knowledge</h2>
        <p className="muted">Health of the document knowledge store (RAG).</p>
      </div>

      <div className="kpi-grid">
        <StatCard label="Projects" value={d.projects} icon="🏢" />
        <StatCard label="Documents" value={d.documents} icon="📄" />
        <StatCard label="Chunks" value={d.chunks} icon="🧩" />
        <StatCard label="Embeddings" value={d.embeddings} icon="🔢" />
      </div>
      <div className="kpi-grid">
        <StatCard label="Processed" value={d.processed} sub="fully indexed" icon="✅" />
        <StatCard label="Pending" value={d.pending} sub="awaiting processing" icon="⏳" />
        <StatCard label="Failed" value={d.failed} sub="review in audit logs" icon="⚠️" tone={d.failed > 0 ? "warn" : ""} />
        <StatCard label="Coverage" value={`${d.coverage}%`} sub="processed vs total" icon="📊" tone={d.coverage < 100 ? "warn" : ""} />
      </div>

      <div className="dash-cols">
        <section className="dash-card">
          <div className="block-title">Recent uploads</div>
          {d.recent_uploads.length === 0 && <div className="muted">No documents uploaded yet.</div>}
          {d.recent_uploads.map((u, i) => (
            <div className="list-row" key={i}>
              <span>{u.title} <span className="muted small">· {u.project}</span></span>
              <StatusPill status={u.status} />
            </div>
          ))}
        </section>
        <section className="dash-card">
          <div className="block-title">Recent processing jobs</div>
          {d.recent_jobs.length === 0 && <div className="muted">No jobs yet.</div>}
          {d.recent_jobs.map((j, i) => (
            <div className="list-row" key={i}>
              <span className="mono">{j.job}</span>
              <StatusPill status={j.status} />
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, icon, tone }) {
  return (
    <div className={`kpi ${tone === "warn" ? "kpi-warn" : ""}`}>
      <div className="row-between"><div className="kpi-label">{label}</div><span>{icon}</span></div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="muted small">{sub}</div>}
    </div>
  );
}

export function StatusPill({ status }) {
  const cls =
    status === "completed" ? "chip-green" :
    status === "failed" ? "chip-red" :
    status === "processing" ? "chip-amber" : "chip-gray";
  return <span className={`status-chip ${cls}`}>{status}</span>;
}
