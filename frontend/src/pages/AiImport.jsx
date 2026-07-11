import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// AI-assisted data entry: upload brochure -> extract -> review/edit -> save.
export default function AiImport() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => { api.projects().then(setProjects); }, []);

  async function extract(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setMsg(null); setDraft(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.extractDraft(fd);
      setDraft(normalizeDraft(r.draft));
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(false); }
  }

  async function save() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.applyDraft(projectId, toPayload(draft));
      const s = r.applied;
      setMsg({ ok: true, text: `Saved: ${s.fields} fields, ${s.towers} towers, ${s.configurations} configs${s.payment_plan ? ", payment plan" : ""}.` });
      setDraft(null); setFile(null);
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(false); }
  }

  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="settings-note">
        🪄 Upload a brochure PDF — AI reads it and pre-fills the fields below.
        <b> Review and edit everything (especially prices)</b> before saving. Nothing is stored until you click Save.
      </div>

      <form onSubmit={extract}>
        <div className="calc-fields">
          <label className="field"><span>Save into project</span>
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} required>
              <option value="">Select a project…</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="field"><span>Brochure / price-list PDF</span>
            <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} required />
          </label>
        </div>
        <button className="btn btn-primary" disabled={busy || !file}>{busy && !draft ? "Extracting…" : "Extract with AI"}</button>
      </form>

      {draft && (
        <div className="extract-preview">
          <div className="block-title" style={{ marginTop: 20 }}>Review extracted data</div>

          <div className="calc-fields">
            <label className="field"><span>Type</span>
              <select value={draft.project_type || ""} onChange={(e) => setField("project_type", e.target.value)}>
                <option value="">—</option><option>Residential</option><option>Commercial</option><option>Industrial</option>
              </select>
            </label>
            <label className="field"><span>Status</span>
              <select value={draft.project_status || ""} onChange={(e) => setField("project_status", e.target.value)}>
                <option value="">—</option><option>Launched</option><option>Under Construction</option><option>Ready to Move</option><option>Delivered</option>
              </select>
            </label>
            <label className="field"><span>Land parcel</span><input value={draft.land_parcel || ""} onChange={(e) => setField("land_parcel", e.target.value)} /></label>
            <label className="field"><span>Green area</span><input value={draft.green_area || ""} onChange={(e) => setField("green_area", e.target.value)} /></label>
            <label className="field"><span>Possession (YYYY-MM-DD)</span><input value={draft.possession_date || ""} onChange={(e) => setField("possession_date", e.target.value)} /></label>
          </div>

          <EditList title="Towers" rows={draft.towers} onChange={(rows) => setField("towers", rows)}
            cols={[["name", "Name"], ["floors", "Floors", "number"], ["height", "Height"], ["units_per_floor", "Units/floor", "number"]]}
            blank={{ name: "", floors: "", height: "", units_per_floor: "" }} />

          <EditList title="Configurations (⚠️ check prices)" rows={draft.configurations} onChange={(rows) => setField("configurations", rows)}
            cols={[["type", "Type"], ["carpet_area", "Carpet", "number"], ["super_area", "Super", "number"], ["base_price", "Price", "number", true], ["plc", "PLC", "number"], ["gst_percent", "GST%", "number"]]}
            blank={{ type: "", carpet_area: "", super_area: "", base_price: "", price_unit: "per_sqft", plc: "", gst_percent: "" }} />

          <div className="block-title" style={{ marginTop: 16 }}>Payment Plan</div>
          <label className="field" style={{ maxWidth: 260 }}><span>Plan name</span>
            <input value={draft.payment_plan?.name || ""} onChange={(e) => setField("payment_plan", { ...draft.payment_plan, name: e.target.value })} />
          </label>
          <EditList rows={draft.payment_plan?.milestones || []} onChange={(rows) => setField("payment_plan", { ...draft.payment_plan, milestones: rows })}
            cols={[["label", "Milestone"], ["percent", "%", "number"]]} blank={{ label: "", percent: "" }} />

          <div style={{ marginTop: 18 }}>
            <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "✓ Save to project"}</button>
            <button className="btn btn-ghost" onClick={() => setDraft(null)}>Discard</button>
          </div>
        </div>
      )}
    </div>
  );
}

// Generic editable list of rows with typed columns; last flag = highlight (price).
function EditList({ title, rows, onChange, cols, blank }) {
  const set = (i, k, v) => onChange(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const del = (i) => onChange(rows.filter((_, j) => j !== i));
  const add = () => onChange([...rows, { ...blank }]);
  return (
    <div style={{ marginTop: 14 }}>
      {title && <div className="block-title">{title}</div>}
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr>{cols.map((c) => <th key={c[0]}>{c[1]}</th>)}<th></th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map(([k, , type, hi]) => (
                  <td key={k} className={hi ? "cell-highlight" : ""}>
                    <input type={type || "text"} value={r[k] ?? ""} onChange={(e) => set(i, k, e.target.value)} style={{ width: type === "number" ? 90 : 130, padding: "5px 7px" }} />
                  </td>
                ))}
                <td><button className="btn btn-ghost" onClick={() => del(i)}>✕</button></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={cols.length + 1} className="muted">None extracted.</td></tr>}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn" style={{ marginTop: 6 }} onClick={add}>+ Add row</button>
    </div>
  );
}

function normalizeDraft(d) {
  return {
    project_type: d.project_type || "", project_status: d.project_status || "",
    land_parcel: d.land_parcel || "", green_area: d.green_area || "", possession_date: d.possession_date || "",
    towers: d.towers || [], configurations: d.configurations || [],
    payment_plan: d.payment_plan || { name: "", milestones: [] },
  };
}

// Convert form strings back to numbers/nulls for the API.
function toPayload(d) {
  const num = (v) => (v === "" || v == null ? null : Number(v));
  return {
    project_type: d.project_type || null, project_status: d.project_status || null,
    land_parcel: d.land_parcel || null, green_area: d.green_area || null,
    possession_date: d.possession_date || null,
    towers: d.towers.filter((t) => t.name).map((t) => ({ name: t.name, floors: num(t.floors), height: t.height || null, units_per_floor: num(t.units_per_floor) })),
    configurations: d.configurations.filter((c) => c.type).map((c) => ({
      type: c.type, carpet_area: num(c.carpet_area), super_area: num(c.super_area),
      base_price: num(c.base_price), price_unit: c.price_unit || "per_sqft", plc: num(c.plc), gst_percent: num(c.gst_percent),
    })),
    payment_plan: d.payment_plan && d.payment_plan.milestones?.length
      ? { name: d.payment_plan.name || null, milestones: d.payment_plan.milestones.filter((m) => m.label).map((m) => ({ label: m.label, percent: Number(m.percent) || 0 })) }
      : null,
  };
}
