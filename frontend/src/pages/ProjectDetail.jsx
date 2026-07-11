import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fetchBlobUrl } from "../api/client.js";
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
  const [towers, setTowers] = useState([]);
  const [brochure, setBrochure] = useState(null);   // {available, title, version}
  const [costSheet, setCostSheet] = useState(null); // {available, title}
  const [pdfUrl, setPdfUrl] = useState(null);        // object URL when viewing
  const [pdfTitle, setPdfTitle] = useState("");
  const [loadingPdf, setLoadingPdf] = useState(false);

  useEffect(() => {
    api.project(id).then(setProject);
    api.projectPrice(id).then(setPrice);
    api.projectPaymentPlan(id).then(setPlan);
    api.projectInventory(id).then(setInv);
    api.brochureInfo(id).then(setBrochure).catch(() => setBrochure({ available: false }));
    api.costSheetInfo(id).then(setCostSheet).catch(() => setCostSheet({ available: false }));
    api.projectTowers(id).then(setTowers).catch(() => setTowers([]));
  }, [id]);

  async function openPdf(path, title) {
    setLoadingPdf(true);
    try {
      setPdfTitle(title);
      setPdfUrl(await fetchBlobUrl(path));
    } catch (e) {
      alert(e.message);
    } finally {
      setLoadingPdf(false);
    }
  }
  function closeBrochure() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(null);
  }

  if (!project) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <Link to="/projects" className="back-link">← Projects</Link>
      <div className="page-head row-between">
        <h2>{project.name}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {brochure?.available && (
            <button className="btn btn-primary" onClick={() => openPdf(`/v1/projects/${id}/brochure`, brochure.title || "Brochure")} disabled={loadingPdf}>
              📄 View Brochure
            </button>
          )}
          {costSheet?.available && (
            <button className="btn" onClick={() => openPdf(`/v1/projects/${id}/cost-sheet`, costSheet.title || "Cost Sheet")} disabled={loadingPdf}>
              💰 View Cost Sheet
            </button>
          )}
          <StatusChip status={project.project_status} />
        </div>
      </div>
      <div className="muted">📍 {project.locality}, {project.city} · Possession {project.possession_date || "—"}</div>

      {(project.project_type || project.land_parcel || project.green_area || towers.length > 0) && (
        <section className="detail-section">
          <h3>Overview</h3>
          <div className="card-grid">
            {project.project_type && <div className="stat-card"><div className="stat-label">Type</div><div className="stat-value" style={{ fontSize: 18 }}>{project.project_type}</div></div>}
            {project.land_parcel && <div className="stat-card"><div className="stat-label">Land parcel</div><div className="stat-value" style={{ fontSize: 18 }}>{project.land_parcel}</div></div>}
            {project.green_area && <div className="stat-card"><div className="stat-label">Green / open area</div><div className="stat-value" style={{ fontSize: 18 }}>{project.green_area}</div></div>}
            <div className="stat-card"><div className="stat-label">Total towers</div><div className="stat-value">{towers.length}</div></div>
          </div>
        </section>
      )}

      {towers.length > 0 && (
        <section className="detail-section">
          <h3>Towers</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Tower</th><th>Floors</th><th>Height</th><th>Units / floor</th></tr></thead>
              <tbody>
                {towers.map((t) => (
                  <tr key={t.id}><td>{t.name}</td><td>{t.floors ?? "—"}</td><td>{t.height || "—"}</td><td>{t.units_per_floor ?? "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {pdfUrl && (
        <div className="pdf-overlay" onClick={closeBrochure}>
          <div className="pdf-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pdf-modal-head">
              <span>{pdfTitle}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <a className="btn btn-ghost" href={pdfUrl} download={`${project.name}-${pdfTitle}.pdf`}>Download</a>
                <button className="btn btn-ghost" onClick={closeBrochure}>✕ Close</button>
              </div>
            </div>
            <iframe className="pdf-frame" src={pdfUrl} title="Brochure" />
          </div>
        </div>
      )}

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
