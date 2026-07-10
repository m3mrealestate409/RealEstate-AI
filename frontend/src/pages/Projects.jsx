import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(search) {
    setLoading(true);
    try {
      setProjects(await api.projects(search));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page">
      <div className="page-head">
        <h2>Projects</h2>
        <p className="muted">Live structured data — every field is the source of truth.</p>
      </div>

      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault();
          load(q);
        }}
      >
        <input placeholder="Search projects…" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn">Search</button>
      </form>

      {loading ? (
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
    status === "Ready to Move" ? "chip-green" :
    status === "Under Construction" ? "chip-amber" : "chip-gray";
  return <span className={`status-chip ${cls}`}>{status || "Unknown"}</span>;
}
