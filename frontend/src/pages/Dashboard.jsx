import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [usage, setUsage] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setErr(e.message));
    api.usage().then(setUsage).catch(() => {});
  }, []);

  if (err) return <div className="page"><div className="alert alert-error">{err}</div></div>;
  if (!d) return <div className="page muted">Loading…</div>;

  const maxDaily = Math.max(1, ...d.daily.map((x) => x.count));
  const maxIntent = Math.max(1, ...d.top_intents.map((x) => x.count));

  return (
    <div className="page">
      <div className="page-head">
        <h2>Analytics</h2>
        <p className="muted">Live usage from the query log.</p>
      </div>

      <div className="kpi-grid">
        <Kpi label="Total queries" value={d.total_queries} />
        <Kpi label="Today" value={d.queries_today} />
        <Kpi label="Miss rate" value={`${d.miss_rate}%`} tone={d.miss_rate > 20 ? "warn" : "ok"} />
        <Kpi label="Avg latency" value={`${d.avg_latency_ms} ms`} tone={d.avg_latency_ms > 3000 ? "warn" : "ok"} />
      </div>

      <div className="dash-cols">
        <section className="dash-card">
          <div className="block-title">Queries (last 7 days)</div>
          <div className="bar-chart">
            {d.daily.map((x) => (
              <div className="bar-col" key={x.date}>
                <div className="bar" style={{ height: `${(x.count / maxDaily) * 100}%` }} title={`${x.count}`}>
                  <span className="bar-val">{x.count || ""}</span>
                </div>
                <div className="bar-label">{x.date.slice(5)}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="dash-card">
          <div className="block-title">Top intents</div>
          {d.top_intents.length === 0 && <div className="muted">No data yet.</div>}
          {d.top_intents.map((x) => (
            <div className="hbar-row" key={x.intent}>
              <div className="hbar-label">{x.intent}</div>
              <div className="hbar-track"><div className="hbar-fill" style={{ width: `${(x.count / maxIntent) * 100}%` }} /></div>
              <div className="hbar-count">{x.count}</div>
            </div>
          ))}
        </section>
      </div>

      <div className="dash-cols">
        <section className="dash-card">
          <div className="block-title">Most-asked projects</div>
          {d.top_projects.length === 0 && <div className="muted">No data yet.</div>}
          {d.top_projects.map((x) => (
            <div className="list-row" key={x.project}>
              <span>{x.project}</span><span className="pill">{x.count}</span>
            </div>
          ))}
        </section>

        <section className="dash-card">
          <div className="block-title">Recent unanswered (knowledge gaps)</div>
          {d.recent_misses.length === 0 && <div className="muted">None — every recent query was answered. 🎉</div>}
          {d.recent_misses.map((m, i) => (
            <div className="miss-row" key={i}>❓ {m.query}</div>
          ))}
        </section>
      </div>

      {usage && (
        <section className="dash-card" style={{ marginTop: 14 }}>
          <div className="row-between">
            <div className="block-title">AI usage today (per employee)</div>
            {usage.company && (
              <span className="muted small">
                Company: {usage.company.used}/{usage.company.limit} ({usage.company.plan} plan)
              </span>
            )}
          </div>
          {usage.employees.length === 0 && <div className="muted">No employees.</div>}
          {usage.employees.map((e, i) => {
            const pct = e.limit ? Math.min(100, Math.round((e.used / e.limit) * 100)) : 0;
            return (
              <div className="usage-row" key={i}>
                <div className="usage-name">{e.name}
                  <span className={`tier-badge tier-${e.tier}`}>{e.tier}</span>
                </div>
                <div className="hbar-track">
                  <div className="hbar-fill" style={{ width: `${pct}%`, background: e.over ? "var(--red)" : undefined }} />
                </div>
                <div className={`usage-count ${e.over ? "usage-over" : ""}`}>{e.used}/{e.limit ?? "∞"}</div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}

function Kpi({ label, value, tone }) {
  return (
    <div className={`kpi ${tone === "warn" ? "kpi-warn" : ""}`}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
