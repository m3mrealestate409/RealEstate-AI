import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);

  // Live search: re-query as the user types. Debounced (250ms) so we don't hit
  // the API on every keystroke; a sequence token drops stale/out-of-order
  // responses so fast typing can never leave the wrong results on screen.
  useEffect(() => {
    const mySeq = ++seq.current;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.projects(q);
        if (mySeq === seq.current) setProjects(res);
      } catch {
        /* transient error — keep the results already on screen */
      } finally {
        if (mySeq === seq.current) setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [q]);

  return (
    <div className="page">
      <div className="page-head">
        <h2>Projects</h2>
        <p className="muted">Live structured data — every field is the source of truth.</p>
      </div>

      {/* Live search — no button needed; results filter as you type. */}
      <form className="search-bar" onSubmit={(e) => e.preventDefault()}>
        <input
          placeholder="Search projects…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
      </form>

      {loading && projects.length === 0 ? (
        <div className="muted">Loading…</div>
      ) : (
        <div className="project-grid">
          {projects.map((p) => (
            <Link to={`/projects/${p.id}`} className="project-card" key={p.id}>
              <div className="project-card-head">
                <h3>{p.name}</h3>
                <StatusChip status={p.project_status} />
              </div>
              <div className="project-loc">📍 {p.locality}, {p.city}</div>
              <div className="project-poss">Possession: {p.possession_date || "—"}</div>
            </Link>
          ))}
          {projects.length === 0 && <div className="muted">No projects found.</div>}
        </div>
      )}
    </div>
  );
}

export function StatusChip({ status }) {
  const cls =
    status === "Ready to Move" || status === "Delivered" ? "chip-green" :
    status === "Under Construction" ? "chip-amber" : "chip-gray";
  return <span className={`status-chip ${cls}`}>{status || "Unknown"}</span>;
}
