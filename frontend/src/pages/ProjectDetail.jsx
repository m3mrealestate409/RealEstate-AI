import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { StatusChip } from "./Projects.jsx";

function money(n) {
  return n == null ? "—" : Number(n).toLocaleString("en-IN");
}

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [price, setPrice] = useState(null);
  const [plan, setPlan] = useState(null);
  const [inv, setInv] = useState(null);

  useEffect(() => {
    api.project(id).then(setProject);
    api.projectPrice(id).then(setPrice);
    api.projectPaymentPlan(id).then(setPlan);
    api.projectInventory(id).then(setInv);
  }, [id]);

  if (!project) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <Link to="/projects" className="back-link">← Projects</Link>
      <div className="page-head row-between">
        <h2>{project.name}</h2>
        <StatusChip status={project.project_status} />
      </div>
      <div className="muted">📍 {project.locality}, {project.city} · Possession {project.possession_date || "—"}</div>

      <section className="detail-section">
        <h3>Price <SourceTag>SQL</SourceTag></h3>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Config</th><th>Carpet</th><th>Base Price</th><th>Unit</th><th>PLC</th><th>GST%</th></tr></thead>
            <tbody>
              {price?.prices?.map((p, i) => (
                <tr key={i}>
                  <td>{p.configuration}</td><td>{money(p.carpet_area)}</td>
                  <td>₹{money(p.base_price)}</td><td>{p.price_unit}</td>
                  <td>₹{money(p.plc)}</td><td>{p.gst_percent}</td>
                </tr>
              )) || <tr><td colSpan="6" className="muted">—</td></tr>}
            </tbody>
          </table>
        </div>
        {price?.last_updated && <div className="updated-note">Last updated {String(price.last_updated).slice(0,10)}</div>}
      </section>

      <section className="detail-section">
        <h3>Payment Plan <SourceTag>SQL</SourceTag></h3>
        <div className="card-grid">
          {plan?.payment_plans?.map((pp, i) => (
            <div className="info-card" key={i}>
              <div className="info-card-head">{pp.name}</div>
              <div className="info-card-sub">{pp.description}</div>
              <ul className="info-card-list">
                {pp.milestones.map((m, j) => <li key={j}>{m.label}: {m.percent}%</li>)}
              </ul>
            </div>
          )) || <div className="muted">—</div>}
        </div>
      </section>

      <section className="detail-section">
        <h3>Inventory <SourceTag>SQL</SourceTag></h3>
        <div className="card-grid">
          {inv?.inventory?.map((r, i) => (
            <div className="stat-card" key={i}>
              <div className="stat-label">{r.configuration}</div>
              <div className="stat-value">{r.available_units}<span className="stat-of"> / {r.total_units}</span></div>
              <div className="stat-sub">units available</div>
            </div>
          )) || <div className="muted">—</div>}
        </div>
      </section>
    </div>
  );
}

function SourceTag({ children }) {
  return <span className="source-tag">{children}</span>;
}
