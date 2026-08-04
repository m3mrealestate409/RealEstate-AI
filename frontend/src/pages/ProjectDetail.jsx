import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fetchBlob, fetchBlobUrl } from "../api/client.js";
import { StatusChip } from "./Projects.jsx";
import Icon from "../components/Icons.jsx";

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
  const [location, setLocation] = useState([]);
  const [amenities, setAmenities] = useState(null); // {found, grouped, amenities}
  const [brochure, setBrochure] = useState(null);   // {available, title, version}
  const [sitePlan, setSitePlan] = useState(null);   // {available, title, version}
  const [costSheets, setCostSheets] = useState([]); // [{id, title, uploaded_at}]
  const [selectedSheet, setSelectedSheet] = useState(""); // selected cost sheet id
  const [showLaunch, setShowLaunch] = useState(false);   // eye toggle for launch price
  const [pdfUrl, setPdfUrl] = useState(null);        // object URL when viewing
  const [pdfTitle, setPdfTitle] = useState("");
  const [loadingPdf, setLoadingPdf] = useState(false);

  useEffect(() => {
    api.project(id).then(setProject);
    api.projectPrice(id).then(setPrice);
    api.projectPaymentPlan(id).then(setPlan);
    api.projectInventory(id).then(setInv);
    api.brochureInfo(id).then(setBrochure).catch(() => setBrochure({ available: false }));
    api.sitePlanInfo(id).then(setSitePlan).catch(() => setSitePlan({ available: false }));
    api.listCostSheets(id).then((list) => {
      setCostSheets(list);
      if (list[0]) setSelectedSheet(String(list[0].id));
    }).catch(() => setCostSheets([]));
    api.projectTowers(id).then(setTowers).catch(() => setTowers([]));
    api.projectLocation(id).then(setLocation).catch(() => setLocation([]));
    api.projectAmenities(id).then(setAmenities).catch(() => setAmenities(null));
  }, [id]);

  // View a protected PDF. The route needs a Bearer header, so we fetch the file
  // as a blob first (a plain link/iframe can't send the token). Desktop shows it
  // in the in-app modal below. On touch devices we instead open it in a NEW TAB,
  // because iOS Safari renders a blob: PDF inside an <iframe> BLANK once the file
  // grows past a few hundred KB — which is exactly why the big brochure / site
  // plan wouldn't open on mobile while the tiny cost sheet did. In a new tab iOS
  // uses its native PDF viewer, which handles any size. The tab is opened
  // synchronously inside the tap so iOS doesn't block it as a popup.
  async function openPdf(path, title) {
    const nativeTab =
      window.matchMedia("(pointer: coarse)").matches ||
      window.matchMedia("(max-width: 860px)").matches;
    let win = null;
    if (nativeTab) {
      win = window.open("", "_blank");
      if (win) win.document.write("<!doctype html><title>Loading…</title>" +
        "<body style='font:16px sans-serif;padding:24px;color:#333'>Loading… please wait.");
    }
    setLoadingPdf(true);
    setPdfTitle(title);
    try {
      const url = await fetchBlobUrl(path);
      if (nativeTab) {
        if (win) win.location = url;
        else window.location.href = url; // popup blocked → fall back to same tab
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      } else {
        setPdfUrl(url);
      }
    } catch (e) {
      if (win) win.close();
      alert(e.message || "Could not open the file");
    } finally {
      setLoadingPdf(false);
    }
  }
  function closeBrochure() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(null);
  }

  // Share a PDF to WhatsApp (and other apps). On mobile the actual file is shared
  // via the native share sheet; on desktop we download it and open WhatsApp Web.
  const [sharing, setSharing] = useState(false);
  async function sharePdf(path, filename, message) {
    setSharing(true);
    try {
      const blob = await fetchBlob(path);
      const file = new File([blob], filename, { type: "application/pdf" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: filename, text: message });
      } else {
        // Desktop fallback: download + open WhatsApp with a prefilled message.
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = filename; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank");
      }
    } catch (e) {
      if (e.name !== "AbortError") alert(e.message || "Could not share");
    } finally {
      setSharing(false);
    }
  }

  if (!project) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <Link to="/projects" className="back-link">← Projects</Link>
      <div className="detail-header">
        <div className="detail-header-main">
      <div className="page-head">
        <div className="title-row">
          <h2>{project.name}</h2>
          {project.rise_type && <span className="rise-badge">{project.rise_type}</span>}
          <StatusChip status={project.project_status} />
        </div>
      </div>
      {project.builder_name && <div className="builder-line">🏗️ by {project.builder_name}</div>}
      <div className="muted">📍 {project.locality}, {project.city} · Possession {project.possession_date || "—"}</div>

      {(project.launch_price != null || project.launch_date) && (
        <div className="launch-highlight">
          🚀 <b>Launch Price</b>
          <button type="button" className="eye-btn" onClick={() => setShowLaunch((v) => !v)}
                  title={showLaunch ? "Hide" : "Show"} aria-label={showLaunch ? "Hide" : "Show"}>
            <Icon name={showLaunch ? "eye-off" : "eye"} size={16} />
          </button>
          {showLaunch && (
            <span>
              {project.launch_price != null && <span>₹{money(project.launch_price)}/sq ft</span>}
              {project.launch_price != null && project.launch_date && <span> · </span>}
              {project.launch_date && <span>Launch Year {String(project.launch_date).slice(0, 4)}</span>}
            </span>
          )}
        </div>
      )}
        </div>

        {(brochure?.available || sitePlan?.available || costSheets.length > 0) && (
          <div className="detail-header-docs">
        <div className="doc-panel">
          {brochure?.available && (
            <div className="doc-row">
              <div className="doc-row-main">
                <span className="doc-ico">📄</span>
                <span className="doc-name">Brochure</span>
              </div>
              <div className="doc-row-actions">
                <button className="btn btn-sm" disabled={loadingPdf}
                  onClick={() => openPdf(`/v1/projects/${id}/brochure`, brochure.title || "Brochure")}>View</button>
                <button className="share-btn" disabled={sharing} title="Share on WhatsApp" aria-label="Share on WhatsApp"
                  onClick={() => sharePdf(`/v1/projects/${id}/brochure`, `${project.name} Brochure.pdf`, `Hi! Please find the ${project.name} brochure attached.`)}>
                  <Icon name="share" size={16} />
                </button>
              </div>
            </div>
          )}
          {sitePlan?.available && (
            <div className="doc-row">
              <div className="doc-row-main">
                <span className="doc-ico">🗺️</span>
                <span className="doc-name">Site Plan</span>
              </div>
              <div className="doc-row-actions">
                <button className="btn btn-sm" disabled={loadingPdf}
                  onClick={() => openPdf(`/v1/projects/${id}/site-plan`, sitePlan.title || "Site Plan")}>View</button>
                <button className="share-btn" disabled={sharing} title="Share on WhatsApp" aria-label="Share on WhatsApp"
                  onClick={() => sharePdf(`/v1/projects/${id}/site-plan`, `${project.name} Site Plan.pdf`, `Hi! Please find the ${project.name} site plan attached.`)}>
                  <Icon name="share" size={16} />
                </button>
              </div>
            </div>
          )}
          {costSheets.length > 0 && (
            <div className="doc-row">
              <div className="doc-row-main">
                <span className="doc-ico">💰</span>
                <span className="doc-name">Cost Sheet</span>
                {costSheets.length > 1 ? (
                  <select className="doc-select" value={selectedSheet} onChange={(e) => setSelectedSheet(e.target.value)}>
                    {costSheets.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
                  </select>
                ) : (
                  <span className="doc-sub">{costSheets[0].title}</span>
                )}
              </div>
              <div className="doc-row-actions">
                <button className="btn btn-sm" disabled={loadingPdf} onClick={() => {
                  const s = costSheets.find((x) => String(x.id) === String(selectedSheet)) || costSheets[0];
                  openPdf(`/v1/projects/${id}/cost-sheets/${s.id}`, s.title || "Cost Sheet");
                }}>View</button>
                <button className="share-btn" disabled={sharing} title="Share on WhatsApp" aria-label="Share on WhatsApp" onClick={() => {
                  const s = costSheets.find((x) => String(x.id) === String(selectedSheet)) || costSheets[0];
                  sharePdf(`/v1/projects/${id}/cost-sheets/${s.id}`, `${s.title}.pdf`, `Hi! Please find the ${project.name} cost sheet (${s.title}) attached.`);
                }}>
                  <Icon name="share" size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
          </div>
        )}
      </div>

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

      {loadingPdf && !pdfUrl && (
        <div className="pdf-overlay">
          <div className="pdf-loading"><span className="pdf-spinner" /> Loading {pdfTitle || "document"}…</div>
        </div>
      )}

      {location.length > 0 && (
        <section className="detail-section">
          <h3>Location & Connectivity</h3>
          <div className="card-grid">
            {[["nearby", "Nearby"], ["connectivity", "Connectivity"], ["upcoming", "Upcoming Development"]].map(([cat, label]) => {
              const items = location.filter((p) => p.category === cat);
              if (items.length === 0) return null;
              return (
                <div className="info-card" key={cat}>
                  <div className="info-card-head">{label}</div>
                  <ul className="info-card-list">
                    {items.map((p) => (
                      <li key={p.id}>{p.name}{p.distance ? <span className="muted"> — {p.distance}</span> : null}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {amenities?.found && (
        <section className="detail-section">
          <h3>Amenities <SourceTag>SQL</SourceTag></h3>
          <div className="card-grid">
            {Object.entries(amenities.grouped || {}).map(([cat, names]) => (
              <div className="info-card" key={cat}>
                <div className="info-card-head">{cat}</div>
                <ul className="info-card-list">
                  {names.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="detail-section">
        <h3>Price <SourceTag>SQL</SourceTag></h3>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Config</th><th>Plan</th><th>Base Price</th><th>Size</th><th>Unit</th><th>PLC</th><th>GST%</th></tr></thead>
            <tbody>
              {price?.prices?.flatMap((p, i) => {
                const trs = [];
                if (p.base_price != null || !(p.plans?.length))
                  trs.push(
                    <tr key={`${i}-b`}>
                      <td>{p.configuration}</td><td className="muted">BSP</td>
                      <td>₹{money(p.base_price)}</td><td>{money(p.size)}</td><td>{p.price_unit}</td>
                      <td>₹{money(p.plc)}</td><td>{p.gst_percent}</td>
                    </tr>
                  );
                (p.plans || []).forEach((pl, j) =>
                  trs.push(
                    <tr key={`${i}-p${j}`}>
                      <td></td><td>{pl.plan}</td>
                      <td>₹{money(pl.base_price)}</td><td></td><td>{pl.price_unit}</td>
                      <td>₹{money(pl.plc)}</td><td>{pl.gst_percent}</td>
                    </tr>
                  )
                );
                return trs;
              }) || <tr><td colSpan="7" className="muted">—</td></tr>}
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
