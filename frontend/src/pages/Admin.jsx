import { useEffect, useState } from "react";
import { api, fetchBlobUrl } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import AiSettings from "./AiSettings.jsx";
import AiImport from "./AiImport.jsx";
import Integrations from "./Integrations.jsx";
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
  const { user } = useAuth();
  const isSuper = user?.is_super_admin === true;
  const [tab, setTab] = useState(isSuper ? "ai" : "import-ai");
  return (
    <div className="page">
      <div className="page-head">
        <h2>Admin</h2>
        <p className="muted">Manage projects, upload brochures, review the audit trail.</p>
      </div>
      <div className="calc-tabs">
        {isSuper && <button className={`tab ${tab === "ai" ? "tab-active" : ""}`} onClick={() => setTab("ai")}>🤖 AI Settings</button>}
        <button className={`tab ${tab === "import-ai" ? "tab-active" : ""}`} onClick={() => setTab("import-ai")}>🪄 AI Import</button>
        <button className={`tab ${tab === "project" ? "tab-active" : ""}`} onClick={() => setTab("project")}>New Project</button>
        <button className={`tab ${tab === "data" ? "tab-active" : ""}`} onClick={() => setTab("data")}>Manage Data</button>
        <button className={`tab ${tab === "document" ? "tab-active" : ""}`} onClick={() => setTab("document")}>Upload Brochure</button>
        <button className={`tab ${tab === "documents" ? "tab-active" : ""}`} onClick={() => setTab("documents")}>Documents</button>
        <button className={`tab ${tab === "builders" ? "tab-active" : ""}`} onClick={() => setTab("builders")}>Developers</button>
        <button className={`tab ${tab === "doctypes" ? "tab-active" : ""}`} onClick={() => setTab("doctypes")}>Doc Types</button>
        <button className={`tab ${tab === "import" ? "tab-active" : ""}`} onClick={() => setTab("import")}>Import CSV</button>
        <button className={`tab ${tab === "users" ? "tab-active" : ""}`} onClick={() => setTab("users")}>Users</button>
        <button className={`tab ${tab === "insights" ? "tab-active" : ""}`} onClick={() => setTab("insights")}>📊 Insights</button>
        <button className={`tab ${tab === "leads" ? "tab-active" : ""}`} onClick={() => setTab("leads")}>📇 Leads</button>
        <button className={`tab ${tab === "apikeys" ? "tab-active" : ""}`} onClick={() => setTab("apikeys")}>🔌 API Keys</button>
        <button className={`tab ${tab === "integrations" ? "tab-active" : ""}`} onClick={() => setTab("integrations")}>🧩 Integrations</button>
        <button className={`tab ${tab === "audit" ? "tab-active" : ""}`} onClick={() => setTab("audit")}>Audit Log</button>
      </div>
      {tab === "ai" && isSuper && <AiSettings />}
      {tab === "import-ai" && <AiImport />}
      {tab === "project" && <NewProject />}
      {tab === "data" && <ManageData />}
      {tab === "document" && <UploadDoc />}
      {tab === "documents" && <DocumentsList />}
      {tab === "builders" && <Builders />}
      {tab === "doctypes" && <DocTypes />}
      {tab === "import" && <ImportCsv />}
      {tab === "users" && <Users />}
      {tab === "insights" && <Insights />}
      {tab === "leads" && <Leads />}
      {tab === "apikeys" && <ApiKeys />}
      {tab === "integrations" && <Integrations />}
      {tab === "audit" && <AuditLog />}
    </div>
  );
}

const STATUS_OPTIONS = ["Launched", "Under Construction", "Ready to Move", "Delivered"];
const TYPE_OPTIONS = ["Residential", "Commercial", "Industrial"];
const RISE_OPTIONS = ["High Rise", "Mid Rise", "Low Rise"];
const BLANK_PROJECT = {
  name: "", slug: "", builder_id: "", city: "", locality: "", project_status: "Under Construction",
  project_type: "Residential", land_parcel: "", green_area: "",
  rise_type: "", launch_date: "", launch_price: "",
};

// builder_id comes from a <select> as a string; the API wants int|null.
// Empty date/number/rise fields must be sent as null (not "") so the API validates.
function cleanProject(f) {
  return {
    ...f,
    builder_id: f.builder_id ? Number(f.builder_id) : null,
    rise_type: f.rise_type || null,
    launch_date: f.launch_date || null,
    launch_price: f.launch_price === "" || f.launch_price == null ? null : Number(f.launch_price),
  };
}

function ProjectFields({ f, set }) {
  const [builders, setBuilders] = useState([]);
  useEffect(() => { api.listBuilders().then(setBuilders).catch(() => setBuilders([])); }, []);
  return (
    <div className="calc-fields">
      <label className="field"><span>Name</span><input value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
      {"slug" in f && <label className="field"><span>Slug (unique)</span><input value={f.slug} onChange={(e) => set("slug", e.target.value)} required /></label>}
      <label className="field"><span>Developer</span>
        <select value={f.builder_id || ""} onChange={(e) => set("builder_id", e.target.value)}>
          <option value="">— None —</option>
          {builders.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </label>
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
      <label className="field"><span>Rise type</span>
        <select value={f.rise_type || ""} onChange={(e) => set("rise_type", e.target.value)}>
          <option value="">— None —</option>
          {RISE_OPTIONS.map((r) => <option key={r}>{r}</option>)}
        </select>
      </label>
      <label className="field"><span>Launch date</span><input type="date" value={f.launch_date || ""} onChange={(e) => set("launch_date", e.target.value)} /></label>
      <label className="field"><span>Launch price (₹/sq ft)</span><input type="number" placeholder="e.g. 7500" value={f.launch_price ?? ""} onChange={(e) => set("launch_price", e.target.value)} /></label>
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
      const p = await api.createProject(cleanProject(f));
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
    try { await api.createBuilder(f); setF({ name: "", rera_id: "" }); await load(); setMsg({ ok: true, text: "Developer added." }); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  async function remove(b) {
    if (!confirm(`Delete developer "${b.name}"?`)) return;
    setMsg(null);
    try { await api.deleteBuilder(b.id); await load(); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <form onSubmit={create}>
        <div className="calc-fields">
          <label className="field"><span>Developer name</span><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></label>
          <label className="field"><span>RERA ID</span><input value={f.rera_id} onChange={(e) => setF({ ...f, rera_id: e.target.value })} /></label>
        </div>
        <button className="btn btn-primary">Add developer</button>
      </form>
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Name</th><th>RERA ID</th><th>Projects</th><th></th></tr></thead>
          <tbody>
            {builders.map((b) => (
              <tr key={b.id}>
                <td>{b.name}</td><td>{b.rera_id || "—"}</td><td>{b.projects}</td>
                <td><button className="btn btn-ghost" onClick={() => remove(b)}>Delete</button></td>
              </tr>
            ))}
            {builders.length === 0 && <tr><td colSpan="4" className="muted">No developers yet.</td></tr>}
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
            <button className={`tab ${sub === "location" ? "tab-active" : ""}`} onClick={() => setSub("location")}>Location</button>
            <button className={`tab ${sub === "amenities" ? "tab-active" : ""}`} onClick={() => setSub("amenities")}>Amenities</button>
            <button className={`tab ${sub === "edit" ? "tab-active" : ""}`} onClick={() => setSub("edit")}>Update Price / Stock</button>
            <button className={`tab ${sub === "config" ? "tab-active" : ""}`} onClick={() => setSub("config")}>Add Configuration</button>
            <button className={`tab ${sub === "plan" ? "tab-active" : ""}`} onClick={() => setSub("plan")}>Add Payment Plan</button>
            <button className={`tab ${sub === "costsheet" ? "tab-active" : ""}`} onClick={() => setSub("costsheet")}>Cost Sheet</button>
          </div>
          {sub === "details" && <EditProjectDetails projectId={projectId} />}
          {sub === "towers" && <Towers projectId={projectId} />}
          {sub === "location" && <LocationPoints projectId={projectId} />}
          {sub === "amenities" && <Amenities projectId={projectId} />}
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
    name: p.name, builder_id: p.builder_id || "", city: p.city || "", locality: p.locality || "",
    project_status: p.project_status || "Under Construction",
    project_type: p.project_type || "Residential",
    land_parcel: p.land_parcel || "", green_area: p.green_area || "",
    rise_type: p.rise_type || "", launch_date: p.launch_date || "",
    launch_price: p.launch_price ?? "",
  })); }, [projectId]);

  if (!f) return <div className="muted">Loading…</div>;

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    try {
      await api.updateProject(projectId, cleanProject(f));
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

const LOC_CATEGORIES = [["nearby", "Nearby"], ["connectivity", "Connectivity"], ["upcoming", "Upcoming Development"]];

function LocationPoints({ projectId }) {
  const [points, setPoints] = useState([]);
  const [f, setF] = useState({ category: "nearby", name: "", distance: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const load = () => api.listLocation(projectId).then(setPoints);
  useEffect(() => { load(); }, [projectId]);

  async function add(e) {
    e.preventDefault(); setMsg(null);
    try {
      await api.addLocation(projectId, { category: f.category, name: f.name, distance: f.distance || null });
      setF({ category: f.category, name: "", distance: "" });
      await load(); setMsg({ ok: true, text: "Location point added." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  async function remove(id) { if (confirm("Delete this location point?")) { await api.deleteLocation(id); load(); } }

  const label = (c) => (LOC_CATEGORIES.find((x) => x[0] === c) || [c, c])[1];

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <form onSubmit={add}>
        <div className="calc-fields">
          <label className="field"><span>Category</span>
            <select value={f.category} onChange={(e) => set("category", e.target.value)}>
              {LOC_CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Name / place</span><input placeholder="DPS School, Metro Station…" value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
          <label className="field"><span>Distance (optional)</span><input placeholder="2 km / 10 min" value={f.distance} onChange={(e) => set("distance", e.target.value)} /></label>
        </div>
        <button className="btn btn-primary">Add location point</button>
      </form>
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Category</th><th>Place</th><th>Distance</th><th></th></tr></thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.id}>
                <td>{label(p.category)}</td><td>{p.name}</td><td>{p.distance || "—"}</td>
                <td><button className="btn btn-ghost" onClick={() => remove(p.id)}>Delete</button></td>
              </tr>
            ))}
            {points.length === 0 && <tr><td colSpan="4" className="muted">No location points yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Amenities({ projectId }) {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ name: "", category: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const load = () => api.listAmenities(projectId).then(setRows);
  useEffect(() => { load(); }, [projectId]);

  async function add(e) {
    e.preventDefault(); setMsg(null);
    try {
      await api.addAmenity(projectId, { name: f.name, category: f.category || null });
      setF({ name: "", category: f.category });
      await load(); setMsg({ ok: true, text: "Amenity added." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  async function remove(id) { if (confirm("Delete this amenity?")) { await api.deleteAmenity(id); load(); } }

  return (
    <div className="admin-form">
      <div className="settings-note">
        Amenities are stored in the database (SQL-first). AI Import fills them from the brochure <b>once</b>;
        after that they always come from the DB — no AI call per query. Add/remove here anytime.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <form onSubmit={add}>
        <div className="calc-fields">
          <label className="field"><span>Amenity</span><input placeholder="Swimming Pool, Clubhouse…" value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
          <label className="field"><span>Category (optional)</span><input placeholder="Sports / Leisure / Safety…" value={f.category} onChange={(e) => set("category", e.target.value)} /></label>
        </div>
        <button className="btn btn-primary">Add amenity</button>
      </form>
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Amenity</th><th>Category</th><th></th></tr></thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td><td>{a.category || "—"}</td>
                <td><button className="btn btn-ghost" onClick={() => remove(a.id)}>Delete</button></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan="3" className="muted">No amenities yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostSheet({ projectId }) {
  const [sheets, setSheets] = useState([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [fileKey, setFileKey] = useState(0);   // to reset the file input
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = () => api.listCostSheets(projectId).then(setSheets).catch(() => setSheets([]));
  useEffect(() => { load(); }, [projectId]);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title.trim());
    try {
      const r = await api.uploadCostSheet(projectId, fd);
      setFile(null); setTitle(""); setFileKey((k) => k + 1);
      await load();
      setMsg({ ok: true, text: `Uploaded "${r.title}".` });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(false); }
  }
  async function remove(s) {
    if (!confirm(`Delete cost sheet "${s.title}"?`)) return;
    try { await api.deleteCostSheet(projectId, s.id); await load(); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <form className="admin-form" onSubmit={upload}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="settings-note">
        Cost sheets are <b>optional</b> and <b>multiple</b> are allowed. Give each a title — they show in a
        dropdown on the project page for viewing/download. Not used for AI answers.
      </div>

      {sheets.length > 0 && (
        <div className="table-wrap" style={{ marginBottom: 16 }}>
          <table className="data-table">
            <thead><tr><th>Title</th><th>Uploaded</th><th></th></tr></thead>
            <tbody>
              {sheets.map((s) => (
                <tr key={s.id}>
                  <td>{s.title}</td>
                  <td className="muted">{s.uploaded_at ? String(s.uploaded_at).slice(0, 10) : "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <a className="btn btn-ghost" href="#" onClick={(e) => { e.preventDefault(); openDoc(`/v1/projects/${projectId}/cost-sheets/${s.id}`); }}>View</a>
                    <button type="button" className="btn btn-ghost btn-danger" onClick={() => remove(s)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="calc-fields">
        <label className="field"><span>Title (e.g. "3BHK Cost Sheet")</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Optional — defaults to project name" />
        </label>
        <label className="field"><span>Cost sheet PDF</span>
          <input key={fileKey} type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} />
        </label>
      </div>
      <button className="btn btn-primary" disabled={busy || !file}>{busy ? "Uploading…" : "Upload cost sheet"}</button>
    </form>
  );
}

function EditConfigs({ projectId }) {
  const [configs, setConfigs] = useState([]);
  const [plans, setPlans] = useState([]);
  const [msg, setMsg] = useState(null);
  const load = () => api.listConfigurations(projectId).then(setConfigs);
  useEffect(() => {
    load();
    api.listPaymentPlans(projectId).then(setPlans).catch(() => setPlans([]));
  }, [projectId]);

  if (configs.length === 0)
    return <div className="muted">No configurations yet. Use "Add Configuration" first.</div>;

  return (
    <div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="edit-config-list">
        {configs.map((c) => (
          <EditConfigRow key={c.id} config={c} plans={plans} onDone={(m) => { setMsg(m); load(); }} />
        ))}
      </div>
    </div>
  );
}

function EditConfigRow({ config, plans = [], onDone }) {
  const [avail, setAvail] = useState(config.inventory?.available_units ?? "");
  const [saving, setSaving] = useState(false);

  // Which price we're editing: "" = base, else a payment_plan_id (as string).
  const [target, setTarget] = useState("");
  const priceFor = (t) => {
    if (!t) return config.current_price?.base_price ?? "";
    const pp = (config.plan_prices || []).find((x) => String(x.payment_plan_id) === String(t));
    return pp?.base_price ?? "";
  };
  const [price, setPrice] = useState(priceFor(""));

  function changeTarget(t) { setTarget(t); setPrice(priceFor(t)); }

  async function savePrice() {
    setSaving(true);
    try {
      const cp = config.current_price || {};
      await api.updatePrice(config.id, {
        base_price: Number(price),
        price_unit: cp.price_unit || "per_sqft",
        // Plan overrides inherit PLC/GST from the base price → send null.
        plc: target ? null : (cp.plc ?? null),
        gst_percent: target ? null : (cp.gst_percent ?? null),
        payment_plan_id: target ? Number(target) : null,
      });
      const label = target ? (plans.find((p) => String(p.id) === String(target))?.name || "plan") : "base";
      onDone({ ok: true, text: `${config.type} · ${label}: price updated to ${Number(price).toLocaleString("en-IN")} (old price kept in history).` });
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

  const priceChanged = String(price) !== String(priceFor(target));
  const stockChanged = String(avail) !== String(config.inventory?.available_units ?? "");

  return (
    <div className="edit-config-row">
      <div className="ecr-title">{config.type}
        <span className="muted small"> · base from {config.current_price?.effective_from || "—"}</span>
      </div>

      {(config.plan_prices || []).length > 0 && (
        <div className="ecr-planprices">
          {config.plan_prices.map((pp) => (
            <span key={pp.payment_plan_id} className="chip chip-sm">
              {pp.plan}: ₹{Number(pp.base_price).toLocaleString("en-IN")}
            </span>
          ))}
        </div>
      )}

      <div className="ecr-fields">
        <div className="ecr-field">
          <label>Price ({config.current_price?.price_unit || "per_sqft"})</label>
          <div className="ecr-inline">
            {plans.length > 0 && (
              <select value={target} onChange={(e) => changeTarget(e.target.value)}>
                <option value="">Base (all plans)</option>
                {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            )}
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
  const [f, setF] = useState({ type: "3BHK", super_area: "", base_price: "", plc: "", gst_percent: "5", total_units: "", available_units: "" });
  const [msg, setMsg] = useState(null);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setMsg(null);
    const body = { type: f.type, price_unit: "per_sqft" };
    for (const k of ["super_area", "base_price", "plc", "gst_percent", "total_units", "available_units"])
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
        <label className="field"><span>Size (sq ft)</span><input type="number" value={f.super_area} onChange={(e) => set("super_area", e.target.value)} /></label>
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
  const [plans, setPlans] = useState([]);

  const loadPlans = () => api.listPaymentPlans(projectId).then(setPlans).catch(() => setPlans([]));
  useEffect(() => { loadPlans(); }, [projectId]);

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
      loadPlans();
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  async function removePlan(p) {
    if (!window.confirm(`Delete payment plan "${p.name}"? Any prices set only for this plan will also be removed (those configs revert to base price).`)) return;
    setMsg(null);
    try {
      const r = await api.deletePaymentPlan(p.id);
      setMsg({ ok: true, text: r.message });
      loadPlans();
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <form onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      {plans.length > 0 && (
        <div className="existing-plans">
          <div className="muted small" style={{ marginBottom: 6 }}>Existing payment plans</div>
          {plans.map((p) => (
            <div className="existing-plan-row" key={p.id}>
              <span>{p.name}</span>
              <button type="button" className="btn btn-ghost btn-danger" onClick={() => removePlan(p)}>Delete</button>
            </div>
          ))}
        </div>
      )}
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

function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState(null);   // {name, api_key} — shown once
  const [msg, setMsg] = useState(null);
  const load = () => api.listApiKeys().then(setKeys).catch(() => setKeys([]));
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setMsg(null);
    try {
      const r = await api.createApiKey(name.trim());
      setNewKey(r);
      setName("");
      await load();
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  async function revoke(id) {
    if (!confirm("Revoke this API key? Any integration using it will stop working.")) return;
    try { await api.revokeApiKey(id); await load(); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <div className="admin-form">
      <div className="settings-note">
        API keys let external systems (your <b>CRM, WhatsApp bot, voice agent, or any website</b>) call the
        engine. Send the key as an <code>X-API-Key</code> header. A key acts within <b>your organization only</b>.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      {newKey && (
        <div className="alert alert-ok">
          <b>New key "{newKey.name}"</b> — copy it now, it won't be shown again:
          <div className="apikey-reveal">
            <code>{newKey.api_key}</code>
            <button type="button" className="btn btn-sm" onClick={() => navigator.clipboard?.writeText(newKey.api_key)}>Copy</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setNewKey(null)}>Done</button>
          </div>
        </div>
      )}

      <form onSubmit={create}>
        <div className="calc-fields">
          <label className="field"><span>Key name (e.g. "CRM integration")</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="CRM integration" required />
          </label>
        </div>
        <button className="btn btn-primary">Create key</button>
      </form>

      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data-table">
          <thead><tr><th>Name</th><th>Key</th><th>Last used</th><th>Created</th><th></th></tr></thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td className="muted"><code>{k.prefix}…</code></td>
                <td className="muted">{k.last_used_at ? String(k.last_used_at).slice(0, 10) : "—"}</td>
                <td className="muted">{k.created_at ? String(k.created_at).slice(0, 10) : "—"}</td>
                <td><button className="btn btn-ghost btn-danger" onClick={() => revoke(k.id)}>Revoke</button></td>
              </tr>
            ))}
            {keys.length === 0 && <tr><td colSpan="5" className="muted">No API keys yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
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

  function downloadSample() {
    const rows = [
      "name,slug,city,locality,project_status,possession_date",
      "Green Valley,green-valley,Gurugram,Sector 90,Under Construction,2028-06-30",
      "Palm Court,palm-court,Noida,Sector 150,Ready to Move,2026-12-31",
      "Sunrise Enclave,sunrise-enclave,Gurugram,Sector 79,Delivered,2025-03-31",
    ];
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "projects-sample.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <form className="admin-form" onSubmit={submit}>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="settings-note">
        CSV columns: <span className="mono">name, slug, city, locality, project_status, possession_date</span> (YYYY-MM-DD).
        Not sure of the format? Download the sample below and fill it in Excel.
      </div>
      <button type="button" className="btn" style={{ marginBottom: 14 }} onClick={downloadSample}>⬇ Download sample CSV</button>
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

function Insights() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.dashboard().then(setD).catch((e) => setErr(e.message)); }, []);

  if (err) return <div className="alert alert-error">{err}</div>;
  if (!d) return <div className="muted">Loading insights…</div>;

  const maxDaily = Math.max(1, ...d.daily.map((x) => x.count));
  return (
    <div className="admin-form">
      <div className="settings-note">
        What people are asking the assistant — and, most importantly, <b>the questions it couldn't answer</b>.
        Each missed question tells you exactly which data or brochure to add next.
      </div>

      <div className="kpi-row">
        <div className="kpi-card"><div className="kpi-num">{d.total_queries}</div><div className="kpi-label">Total questions</div></div>
        <div className="kpi-card"><div className="kpi-num">{d.queries_today}</div><div className="kpi-label">Today</div></div>
        <div className="kpi-card"><div className={`kpi-num ${d.miss_rate > 20 ? "kpi-warn" : ""}`}>{d.miss_rate}%</div><div className="kpi-label">Unanswered rate</div></div>
        <div className="kpi-card"><div className="kpi-num">{d.avg_latency_ms} ms</div><div className="kpi-label">Avg. response</div></div>
      </div>

      <div className="insight-grid">
        <div className="insight-box">
          <div className="block-title">🚨 Top unanswered questions</div>
          <p className="muted small" style={{ marginTop: 0 }}>Add this data/brochure to close the gap.</p>
          {(d.top_missed || []).length === 0 ? (
            <div className="muted">Nothing missed yet — great coverage! 🎉</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Question</th><th style={{ width: 60 }}>Times</th></tr></thead>
              <tbody>
                {d.top_missed.map((m, i) => (
                  <tr key={i}><td>{m.query}</td><td><span className="conf-badge conf-mid">{m.count}×</span></td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="insight-box">
          <div className="block-title">🔥 Most-asked projects</div>
          {(d.top_projects || []).length === 0 ? (
            <div className="muted">No project questions yet.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Project</th><th style={{ width: 60 }}>Asks</th></tr></thead>
              <tbody>
                {d.top_projects.map((p, i) => (
                  <tr key={i}><td>{p.project}</td><td>{p.count}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="insight-box" style={{ marginTop: 16 }}>
        <div className="block-title">📈 Questions — last 7 days</div>
        <div className="mini-bars">
          {d.daily.map((x, i) => (
            <div className="mini-bar-col" key={i}>
              <div className="mini-bar" style={{ height: `${Math.round((x.count / maxDaily) * 100)}%` }} title={`${x.count}`}></div>
              <div className="mini-bar-x">{x.date.slice(5)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const LEAD_STATUSES = ["new", "contacted", "qualified", "closed"];

function Leads() {
  const [rows, setRows] = useState([]);
  const [webhook, setWebhook] = useState("");
  const [msg, setMsg] = useState(null);
  const [saving, setSaving] = useState(false);
  const load = () => api.listLeads().then(setRows).catch(() => setRows([]));
  useEffect(() => {
    load();
    api.getCrmConfig().then((c) => setWebhook(c.crm_webhook_url || "")).catch(() => {});
  }, []);

  async function saveWebhook() {
    setSaving(true); setMsg(null);
    try {
      const r = await api.setCrmConfig(webhook.trim());
      setWebhook(r.crm_webhook_url || "");
      setMsg({ ok: true, text: "CRM webhook saved — new leads will be pushed there." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  async function changeStatus(id, status) {
    try { await api.updateLeadStatus(id, status); await load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  async function removeLead(l) {
    if (!confirm(`Delete lead ${l.phone || l.name || l.id}? This can't be undone.`)) return;
    try { await api.deleteLead(l.id); await load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }

  return (
    <div className="admin-form">
      <div className="settings-note">
        Prospects captured by the assistant (website widget, CRM, WhatsApp). Optionally push every new lead to
        your own CRM via a <b>webhook</b> — the engine POSTs the lead's details there in real time.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="tier-limits-box">
        <div className="block-title">CRM webhook (optional)</div>
        <div className="muted small" style={{ marginBottom: 8 }}>
          Paste a URL that accepts a POST with JSON. We send: name, phone, email, message, project_interest, source, created_at.
        </div>
        <div className="ecr-inline" style={{ maxWidth: 640 }}>
          <input style={{ flex: 1 }} placeholder="https://your-crm.com/webhooks/leads" value={webhook} onChange={(e) => setWebhook(e.target.value)} />
          <button className="btn btn-primary" onClick={saveWebhook} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        </div>
      </div>

      <div className="table-wrap" style={{ marginTop: 18 }}>
        <table className="data-table">
          <thead><tr><th>When</th><th>Name</th><th>Phone</th><th>Interested in</th><th>Message</th><th>Source</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map((l) => (
              <tr key={l.id}>
                <td className="muted">{l.created_at ? String(l.created_at).slice(0, 16).replace("T", " ") : "—"}</td>
                <td>{l.name || "—"}</td>
                <td>{l.phone ? <a href={`tel:${l.phone}`}>{l.phone}</a> : (l.email || "—")}</td>
                <td>{l.project_interest ? <span className="status-chip chip-green">{l.project_interest}</span> : "—"}</td>
                <td>{l.message || "—"}</td>
                <td><span className="status-chip chip-gray">{l.source}</span></td>
                <td>
                  <select value={l.status} onChange={(e) => changeStatus(l.id, e.target.value)}>
                    {LEAD_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td><button className="btn btn-ghost btn-danger" onClick={() => removeLead(l)}>Delete</button></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan="8" className="muted">No leads yet. They'll appear here as the assistant captures them.</td></tr>}
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
