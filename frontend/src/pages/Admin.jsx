import { useEffect, useState } from "react";
import { api, fetchBlobUrl } from "../api/client.js";
import AiSettings from "./AiSettings.jsx";
import AiImport from "./AiImport.jsx";
import { StatusPill } from "./Knowledge.jsx";

// Open a protected PDF (brochure/cost sheet) in a new tab via authed blob fetch.
async function openDoc(path) {
  try {
    const url = await fetchBlobUrl(path);
    window.open(url, "_blank");
  } catch (e) {
    alert(e.message);
  }
}

export default function Admin() {
  const [tab, setTab] = useState("ai");
  return (
    <div className="page">
      <div className="page-head">
        <h2>Admin</h2>
        <p className="muted">Configure AI, manage projects, upload brochures, review the audit trail.</p>
      </div>
      <div className="calc-tabs">
        <button className={`tab ${tab === "ai" ? "tab-active" : ""}`} onClick={() => setTab("ai")}>🤖 AI Settings</button>
        <button className={`tab ${tab === "import-ai" ? "tab-active" : ""}`} onClick={() => setTab("import-ai")}>🪄 AI Import</button>
        <button className={`tab ${tab === "project" ? "tab-active" : ""}`} onClick={() => setTab("project")}>New Project</button>
        <button className={`tab ${tab === "data" ? "tab-active" : ""}`} onClick={() => setTab("data")}>Manage Data</button>
        <button className={`tab ${tab === "document" ? "tab-active" : ""}`} onClick={() => setTab("document")}>Upload Brochure</button>
        <button className={`tab ${tab === "documents" ? "tab-active" : ""}`} onClick={() => setTab("documents")}>Documents</button>
        <button className={`tab ${tab === "builders" ? "tab-active" : ""}`} onClick={() => setTab("builders")}>Builders</button>
        <button className={`tab ${tab === "doctypes" ? "tab-active" : ""}`} onClick={() => setTab("doctypes")}>Doc Types</button>
        <button className={`tab ${tab === "import" ? "tab-active" : ""}`} onClick={() => setTab("import")}>Import CSV</button>
        <button className={`tab ${tab === "users" ? "tab-active" : ""}`} onClick={() => setTab("users")}>Users</button>
        <button className={`tab ${tab === "audit" ? "tab-active" : ""}`} onClick={() => setTab("audit")}>Audit Log</button>
      </div>
      {tab === "ai" && <AiSettings />}
      {tab === "import-ai" && <AiImport />}
      {tab === "project" && <NewProject />}
      {tab === "data" && <ManageData />}
      {tab === "document" && <UploadDoc />}
      {tab === "documents" && <DocumentsList />}
      {tab === "builders" && <Builders />}
      {tab === "doctypes" && <DocTypes />}
      {tab === "import" && <ImportCsv />}
      {tab === "users" && <Users />}
      {tab === "audit" && <AuditLog />}
    </div>
  );
}

const STATUS_OPTIONS = ["Launched", "Under Construction", "Ready to Move", "Delivered"];
const TYPE_OPTIONS = ["Residential", "Commercial", "Industrial"];
const BLANK_PROJECT = {
  name: "", slug: "", city: "", locality: "", project_status: "Under Construction",
  project_type: "Residential", land_parcel: "", green_area: "",
};

function ProjectFields({ f, set }) {
  return (
    <div className="calc-fields">
      <label className="field"><span>Name</span><input value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
      {"slug" in f && <label className="field"><span>Slug (unique)</span><input value={f.slug} onChange={(e) => set("slug", e.target.value)} required /></label>}
      <label className="field"><span>City</span><input value={f.city || ""} onChange={(e) => set("city", e.target.value)} /></label>
      <label className="field"><span>Locality</span><input value={f.locality || ""} onChange={(e) => set("locality", e.target.value)} /></label>
      <label className="field"><span>Status</span>
        <select value={f.project_status || ""} onChange={(e) => set("project_status", e.target.value)}>
          {STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      <label className="field"><span>Type</span>
        <select value={f.project_type || "Residential"} onChange={(e) => set("project_type", e.target.value)}>
          {TYPE_OPTIONS.map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <label className="field"><span>Land parcel</span><input placeholder="e.g. 18 acres" value={f.land_parcel || ""} onChange={(e) => set("land_parcel", e.target.value)} /></label>
      <label className="field"><span>Green / open area</span><input placeholder="e.g. 72%" value={f.green_area || ""} onChange={(e) => set("green_area", e.target.value)} /></label>
    </div>
  );
}

function NewProject() {
  const [f, setF] = useState(BLANK_PROJECT);
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setMsg(null);
    try {
      const p = await api.createProject(f);
      setMsg({ ok: true, text: `Created "${p.name}" (id ${p.id}).` });
      setF(BLANK_PROJECT);
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <form className="admin-form" onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <ProjectFields f={f} set={set} />
      <button className="btn btn-primary">Create Project</button>
    </form>
  );
}

function UploadDoc() {
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("brochure");
  const [file, setFile] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState([]);

  useEffect(() => { api.projects().then(setProjects); }, []);

  async function submit(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("project_id", projectId);
    fd.append("title", title);
    fd.append("doc_type", docType);
    fd.append("file", file);
    try {
      const res = await api.uploadDocument(fd);
      setMsg({ ok: true, text: `Indexed "${res.title}" — ${res.chunks_indexed} chunks.` });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="admin-form" onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="calc-fields">
        <label className="field"><span>Project</span>
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)} required>
            <option value="">Select…</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="field"><span>Title</span><input value={title} onChange={(e) => setTitle(e.target.value)} required /></label>
        <label className="field"><span>Type</span>
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="brochure">Brochure</option><option value="legal">Legal</option>
            <option value="floor_plan">Floor Plan</option><option value="master_plan">Master Plan</option>
          </select>
        </label>
        <label className="field"><span>PDF file</span><input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} required /></label>
      </div>
      <button className="btn btn-primary" disabled={busy}>{busy ? "Indexing…" : "Upload & Index"}</button>
    </form>
  );
}

function DocumentsList() {
  const [docs, setDocs] = useState([]);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [replacing, setReplacing] = useState(null); // doc id being replaced
  const load = () => api.listDocuments().then(setDocs);
  useEffect(() => { load(); }, []);

  async function reindex(id) {
    setBusy(id); setMsg(null);
    try { const r = await api.reindexDocument(id); setMsg({ ok: true, text: `Re-indexed: ${r.chunks_indexed} chunks (v${r.version}).` }); await load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  }
  async function remove(id) {
    if (!confirm("Delete this document and its chunks?")) return;
    setBusy(id);
    try { await api.deleteDocument(id); await load(); } finally { setBusy(null); }
  }
  async function replaceFile(id, file) {
    if (!file) return;
    setBusy(id); setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.replaceDocument(id, fd);
      setMsg({ ok: true, text: `Replaced with new file — ${r.chunks_indexed} chunks (v${r.version}). Old content deactivated.` });
      setReplacing(null);
      await load();
    } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Title</th><th>Project</th><th>Type</th><th>Status</th><th>Chunks</th><th>Ver</th><th></th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.title}</td><td>{d.project}</td><td>{d.doc_type}</td>
                <td><StatusPill status={d.status} /></td><td>{d.chunks}</td><td>{d.version}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {replacing === d.id ? (
                    <label className="btn btn-primary" style={{ cursor: "pointer" }}>
                      Choose new PDF
                      <input type="file" accept="application/pdf" hidden
                        onChange={(e) => replaceFile(d.id, e.target.files[0])} />
                    </label>
                  ) : (
                    <button className="btn btn-ghost" disabled={busy === d.id} onClick={() => setReplacing(d.id)}>Replace</button>
                  )}
                  <button className="btn btn-ghost" disabled={busy === d.id} onClick={() => reindex(d.id)}>Re-index</button>
                  <button className="btn btn-ghost" disabled={busy === d.id} onClick={() => remove(d.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {docs.length === 0 && <tr><td colSpan="7" className="muted">No documents yet. Upload a brochure first.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ marginTop: 10 }}>
        <b>Replace</b> = upload a new PDF for this document; the old brochure's chunks are deactivated so RAG only uses the latest.
        <b> Re-index</b> = rebuild chunks from the same file (e.g. after switching embeddings).
      </p>
    </div>
  );
}

function Builders() {
  const [builders, setBuilders] = useState([]);
  const [f, setF] = useState({ name: "", rera_id: "" });
  const [msg, setMsg] = useState(null);
  const load = () => api.listBuilders().then(setBuilders);
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault(); setMsg(null);
    try { await api.createBuilder(f); setF({ name: "", rera_id: "" }); await load(); setMsg({ ok: true, text: "Builder added." }); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <form onSubmit={create}>
        <div className="calc-fields">
          <label className="field"><span>Builder name</span><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></label>
          <label className="field"><span>RERA ID</span><input value={f.rera_id} onChange={(e) => setF({ ...f, rera_id: e.target.value })} /></label>
        </div>
        <button className="btn btn-primary">Add builder</button>
      </form>
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Name</th><th>RERA ID</th><th>Projects</th></tr></thead>
          <tbody>
            {builders.map((b) => <tr key={b.id}><td>{b.name}</td><td>{b.rera_id || "—"}</td><td>{b.projects}</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DocTypes() {
  const [types, setTypes] = useState([]);
  const [input, setInput] = useState("");
  const [msg, setMsg] = useState(null);
  useEffect(() => { api.getDocTypes().then((r) => setTypes(r.types)); }, []);

  async function save() {
    setMsg(null);
    try { const r = await api.setDocTypes(types); setTypes(r.types); setMsg({ ok: true, text: "Saved." }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="block-title">Document types used for uploads</div>
      <div className="chip-editor">
        {types.map((t, i) => (
          <span className="chip" key={i}>{t} <button type="button" className="chip-x" onClick={() => setTypes(types.filter((_, j) => j !== i))}>✕</button></span>
        ))}
      </div>
      <div className="search-bar" style={{ maxWidth: 380 }}>
        <input placeholder="Add a type…" value={input} onChange={(e) => setInput(e.target.value)} />
        <button className="btn" onClick={() => { if (input.trim()) { setTypes([...types, input.trim()]); setInput(""); } }}>Add</button>
      </div>
      <button className="btn btn-primary" onClick={save}>Save types</button>
    </div>
  );
}

function ManageData() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [sub, setSub] = useState("details");
  useEffect(() => { api.projects().then(setProjects); }, []);

  return (
    <div className="admin-form">
      <label className="field" style={{ maxWidth: 320 }}>
        <span>Project</span>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">Select a project…</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>

      {projectId && (
        <>
          <div className="calc-tabs">
            <button className={`tab ${sub === "details" ? "tab-active" : ""}`} onClick={() => setSub("details")}>Project Details</button>
            <button className={`tab ${sub === "towers" ? "tab-active" : ""}`} onClick={() => setSub("towers")}>Towers</button>
            <button className={`tab ${sub === "edit" ? "tab-active" : ""}`} onClick={() => setSub("edit")}>Update Price / Stock</button>
            <button className={`tab ${sub === "config" ? "tab-active" : ""}`} onClick={() => setSub("config")}>Add Configuration</button>
            <button className={`tab ${sub === "plan" ? "tab-active" : ""}`} onClick={() => setSub("plan")}>Add Payment Plan</button>
            <button className={`tab ${sub === "costsheet" ? "tab-active" : ""}`} onClick={() => setSub("costsheet")}>Cost Sheet</button>
          </div>
          {sub === "details" && <EditProjectDetails projectId={projectId} />}
          {sub === "towers" && <Towers projectId={projectId} />}
          {sub === "edit" && <EditConfigs projectId={projectId} />}
          {sub === "config" && <AddConfig projectId={projectId} />}
          {sub === "plan" && <AddPlan projectId={projectId} />}
          {sub === "costsheet" && <CostSheet projectId={projectId} />}
        </>
      )}
    </div>
  );
}

function EditProjectDetails({ projectId }) {
  const [f, setF] = useState(null);
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  useEffect(() => { api.project(projectId).then((p) => setF({
    name: p.name, city: p.city || "", locality: p.locality || "",
    project_status: p.project_status || "Under Construction",
    project_type: p.project_type || "Residential",
    land_parcel: p.land_parcel || "", green_area: p.green_area || "",
  })); }, [projectId]);

  if (!f) return <div className="muted">Loading…</div>;

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.updateProject(projectId, f);
      setMsg({ ok: true, text: "Project details saved." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <form className="admin-form" onSubmit={save}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <ProjectFields f={f} set={set} />
      <button className="btn btn-primary">Save details</button>
    </form>
  );
}

function Towers({ projectId }) {
  const [towers, setTowers] = useState([]);
  const [f, setF] = useState({ name: "", floors: "", height: "", units_per_floor: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const load = () => api.listTowers(projectId).then(setTowers);
  useEffect(() => { load(); }, [projectId]);

  async function add(e) {
    e.preventDefault();
    setMsg(null);
    const body = { name: f.name };
    for (const k of ["floors", "units_per_floor"]) if (f[k] !== "") body[k] = Number(f[k]);
    if (f.height) body.height = f.height;
    try {
      await api.addTower(projectId, body);
      setF({ name: "", floors: "", height: "", units_per_floor: "" });
      await load();
      setMsg({ ok: true, text: "Tower added." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  async function remove(id) { if (confirm("Delete this tower?")) { await api.deleteTower(id); load(); } }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <form onSubmit={add}>
        <div className="calc-fields">
          <label className="field"><span>Tower name</span><input placeholder="Tower A" value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
          <label className="field"><span>Floors</span><input type="number" value={f.floors} onChange={(e) => set("floors", e.target.value)} /></label>
          <label className="field"><span>Height</span><input placeholder="140 m / G+40" value={f.height} onChange={(e) => set("height", e.target.value)} /></label>
          <label className="field"><span>Units / floor</span><input type="number" value={f.units_per_floor} onChange={(e) => set("units_per_floor", e.target.value)} /></label>
        </div>
        <button className="btn btn-primary">Add tower</button>
      </form>
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Tower</th><th>Floors</th><th>Height</th><th>Units/floor</th><th></th></tr></thead>
          <tbody>
            {towers.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td><td>{t.floors ?? "—"}</td><td>{t.height || "—"}</td><td>{t.units_per_floor ?? "—"}</td>
                <td><button className="btn btn-ghost" onClick={() => remove(t.id)}>Delete</button></td>
              </tr>
            ))}
            {towers.length === 0 && <tr><td colSpan="5" className="muted">No towers yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostSheet({ projectId }) {
  const [info, setInfo] = useState(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = () => api.costSheetInfo(projectId).then(setInfo).catch(() => setInfo({ available: false }));
  useEffect(() => { load(); }, [projectId]);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.uploadCostSheet(projectId, fd);
      setFile(null);
      await load();
      setMsg({ ok: true, text: "Cost sheet uploaded." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(false); }
  }

  return (
    <form className="admin-form" onSubmit={upload}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="settings-note">
        Cost sheet is <b>optional</b>. If you have one, upload the PDF — it will be viewable/downloadable on the project page.
        It is <b>not</b> used for AI answers (prices come from the structured data).
      </div>
      {info?.available && (
        <div className="alert alert-ok">
          Current cost sheet: <b>{info.title}</b>{" "}
          <a className="btn btn-ghost" style={{ marginLeft: 8 }} href="#" onClick={(e) => { e.preventDefault(); openDoc(`/v1/projects/${projectId}/cost-sheet`); }}>View</a>
          <span className="muted small"> (uploading a new one replaces it)</span>
        </div>
      )}
      <label className="field"><span>Cost sheet PDF</span>
        <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} />
      </label>
      <button className="btn btn-primary" disabled={busy || !file}>{busy ? "Uploading…" : "Upload cost sheet"}</button>
    </form>
  );
}

function EditConfigs({ projectId }) {
  const [configs, setConfigs] = useState([]);
  const [msg, setMsg] = useState(null);
  const load = () => api.listConfigurations(projectId).then(setConfigs);
  useEffect(() => { load(); }, [projectId]);

  if (configs.length === 0)
    return <div className="muted">No configurations yet. Use "Add Configuration" first.</div>;

  return (
    <div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="edit-config-list">
        {configs.map((c) => (
          <EditConfigRow key={c.id} config={c} onDone={(m) => { setMsg(m); load(); }} />
        ))}
      </div>
    </div>
  );
}

function EditConfigRow({ config, onDone }) {
  const [price, setPrice] = useState(config.current_price?.base_price ?? "");
  const [avail, setAvail] = useState(config.inventory?.available_units ?? "");
  const [saving, setSaving] = useState(false);

  async function savePrice() {
    setSaving(true);
    try {
      const cp = config.current_price || {};
      await api.updatePrice(config.id, {
        base_price: Number(price), price_unit: cp.price_unit || "per_sqft",
        plc: cp.plc ?? null, gst_percent: cp.gst_percent ?? null,
      });
      onDone({ ok: true, text: `${config.type}: price updated to ${Number(price).toLocaleString("en-IN")} (old price kept in history).` });
    } catch (e) { onDone({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  async function saveStock() {
    setSaving(true);
    try {
      await api.updateInventory(config.id, { available_units: Number(avail) });
      onDone({ ok: true, text: `${config.type}: available units updated to ${avail}.` });
    } catch (e) { onDone({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }

  const priceChanged = String(price) !== String(config.current_price?.base_price ?? "");
  const stockChanged = String(avail) !== String(config.inventory?.available_units ?? "");

  return (
    <div className="edit-config-row">
      <div className="ecr-title">{config.type}
        <span className="muted small"> · from {config.current_price?.effective_from || "—"}</span>
      </div>
      <div className="ecr-fields">
        <div className="ecr-field">
          <label>Price ({config.current_price?.price_unit || "per_sqft"})</label>
          <div className="ecr-inline">
            <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
            <button className="btn btn-primary" disabled={!priceChanged || saving} onClick={savePrice}>Update</button>
          </div>
        </div>
        <div className="ecr-field">
          <label>Available units</label>
          <div className="ecr-inline">
            <input type="number" value={avail} onChange={(e) => setAvail(e.target.value)} />
            <button className="btn" disabled={!stockChanged || saving} onClick={saveStock}>Update</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AddConfig({ projectId }) {
  const [f, setF] = useState({ type: "3BHK", carpet_area: "", super_area: "", base_price: "", plc: "", gst_percent: "5", total_units: "", available_units: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setMsg(null);
    const body = { type: f.type, price_unit: "per_sqft" };
    for (const k of ["carpet_area", "super_area", "base_price", "plc", "gst_percent", "total_units", "available_units"])
      if (f[k] !== "") body[k] = Number(f[k]);
    try {
      const r = await api.addConfiguration(projectId, body);
      setMsg({ ok: true, text: r.message });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <form onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="calc-fields">
        <label className="field"><span>Type (e.g. 3BHK)</span><input value={f.type} onChange={(e) => set("type", e.target.value)} required /></label>
        <label className="field"><span>Carpet area (sq ft)</span><input type="number" value={f.carpet_area} onChange={(e) => set("carpet_area", e.target.value)} /></label>
        <label className="field"><span>Super area (sq ft)</span><input type="number" value={f.super_area} onChange={(e) => set("super_area", e.target.value)} /></label>
        <label className="field"><span>Base price (₹/sq ft)</span><input type="number" value={f.base_price} onChange={(e) => set("base_price", e.target.value)} required /></label>
        <label className="field"><span>PLC (₹)</span><input type="number" value={f.plc} onChange={(e) => set("plc", e.target.value)} /></label>
        <label className="field"><span>GST %</span><input type="number" value={f.gst_percent} onChange={(e) => set("gst_percent", e.target.value)} /></label>
        <label className="field"><span>Total units</span><input type="number" value={f.total_units} onChange={(e) => set("total_units", e.target.value)} /></label>
        <label className="field"><span>Available units</span><input type="number" value={f.available_units} onChange={(e) => set("available_units", e.target.value)} /></label>
      </div>
      <button className="btn btn-primary">Add configuration</button>
    </form>
  );
}

function AddPlan({ projectId }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [milestones, setMilestones] = useState([{ label: "On Booking", percent: 10 }, { label: "On Possession", percent: 90 }]);
  const [msg, setMsg] = useState(null);

  const total = milestones.reduce((s, m) => s + Number(m.percent || 0), 0);
  function setM(i, k, v) { setMilestones((s) => s.map((m, j) => (j === i ? { ...m, [k]: v } : m))); }

  async function submit(e) {
    e.preventDefault();
    setMsg(null);
    try {
      const r = await api.addPaymentPlan(projectId, {
        name, description: desc,
        milestones: milestones.map((m) => ({ label: m.label, percent: Number(m.percent) })),
      });
      setMsg({ ok: true, text: r.message });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <form onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="calc-fields">
        <label className="field"><span>Plan name (e.g. 10:80:10)</span><input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label className="field"><span>Description</span><input value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
      </div>
      {milestones.map((m, i) => (
        <div className="milestone-row" key={i}>
          <input placeholder="Label" value={m.label} onChange={(e) => setM(i, "label", e.target.value)} />
          <input type="number" placeholder="%" value={m.percent} onChange={(e) => setM(i, "percent", e.target.value)} />
          <button type="button" className="btn btn-ghost" onClick={() => setMilestones((s) => s.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <div className="row-between" style={{ maxWidth: 380, margin: "8px 0" }}>
        <button type="button" className="btn" onClick={() => setMilestones((s) => [...s, { label: "", percent: 0 }])}>+ Milestone</button>
        <span className={total === 100 ? "conf-badge conf-high" : "conf-badge conf-mid"}>Total: {total}%</span>
      </div>
      <button className="btn btn-primary" disabled={total !== 100}>Add payment plan</button>
    </form>
  );
}

function ImportCsv() {
  const [file, setFile] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.importProjectsCsv(fd);
      setMsg({ ok: true, text: `Created ${r.created}, skipped ${r.skipped_existing} existing.${r.errors.length ? " Errors: " + r.errors.join("; ") : ""}` });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(false); }
  }

  return (
    <form className="admin-form" onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="settings-note">
        CSV columns: <span className="mono">name, slug, city, locality, project_status, possession_date</span> (YYYY-MM-DD).
        Export from Excel as CSV.
      </div>
      <label className="field"><span>CSV file</span><input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} required /></label>
      <button className="btn btn-primary" disabled={busy}>{busy ? "Importing…" : "Import projects"}</button>
    </form>
  );
}

function Users() {
  const [users, setUsers] = useState([]);
  const [limits, setLimits] = useState({ basic_daily_limit: "", advanced_daily_limit: "" });
  const [f, setF] = useState({ email: "", name: "", role: "sales", tier: "basic", password: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const load = () => { api.listUsers().then(setUsers); api.getTierLimits().then(setLimits); };
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.createUser(f);
      setF({ email: "", name: "", role: "sales", tier: "basic", password: "" });
      await load();
      setMsg({ ok: true, text: "User created." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  async function toggle(id) { await api.toggleUser(id); load(); }
  async function changeTier(id, tier) { await api.setUserTier(id, tier); load(); }
  async function saveLimits() {
    setMsg(null);
    try {
      const r = await api.setTierLimits({
        basic_daily_limit: Number(limits.basic_daily_limit),
        advanced_daily_limit: Number(limits.advanced_daily_limit),
      });
      setLimits(r);
      setMsg({ ok: true, text: "Tier limits saved." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="tier-limits-box">
        <div className="block-title">Daily AI-query limit per tier</div>
        <div className="muted small" style={{ marginBottom: 8 }}>
          Only AI queries (comparison, summary, amenities) count. Price / inventory look-ups are always free.
        </div>
        <div className="ecr-fields">
          <div className="ecr-field">
            <label>Basic tier</label>
            <input type="number" value={limits.basic_daily_limit ?? ""} onChange={(e) => setLimits({ ...limits, basic_daily_limit: e.target.value })} />
          </div>
          <div className="ecr-field">
            <label>Advanced tier</label>
            <input type="number" value={limits.advanced_daily_limit ?? ""} onChange={(e) => setLimits({ ...limits, advanced_daily_limit: e.target.value })} />
          </div>
          <button type="button" className="btn btn-primary" onClick={saveLimits} style={{ alignSelf: "flex-end" }}>Save limits</button>
        </div>
      </div>

      <form onSubmit={create}>
        <div className="calc-fields">
          <label className="field"><span>Email</span><input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} required /></label>
          <label className="field"><span>Name</span><input value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
          <label className="field"><span>Role</span>
            <select value={f.role} onChange={(e) => set("role", e.target.value)}>
              <option value="sales">sales</option><option value="manager">manager</option><option value="admin">admin</option>
            </select>
          </label>
          <label className="field"><span>Tier (query limit)</span>
            <select value={f.tier} onChange={(e) => set("tier", e.target.value)}>
              <option value="basic">basic</option><option value="advanced">advanced</option>
            </select>
          </label>
          <label className="field"><span>Password</span><input type="password" value={f.password} onChange={(e) => set("password", e.target.value)} required /></label>
        </div>
        <button className="btn btn-primary">Create user</button>
      </form>

      <div className="table-wrap" style={{ marginTop: 18 }}>
        <table className="data-table">
          <thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Tier</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td><td>{u.name || "—"}</td>
                <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                <td>
                  <select value={u.tier || "basic"} onChange={(e) => changeTier(u.id, e.target.value)}>
                    <option value="basic">basic</option><option value="advanced">advanced</option>
                  </select>
                </td>
                <td>{u.is_active === false ? <span className="status-chip chip-gray">inactive</span> : <span className="status-chip chip-green">active</span>}</td>
                <td><button className="btn btn-ghost" onClick={() => toggle(u.id)}>Toggle</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AuditLog() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.audit().then(setRows); }, []);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>ID</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.created_at?.slice(0, 19).replace("T", " ")}</td>
              <td>{r.user_id}</td>
              <td><span className={`audit-action a-${r.action}`}>{r.action}</span></td>
              <td>{r.entity}</td><td>{r.entity_id}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan="5" className="muted">No audit entries yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
