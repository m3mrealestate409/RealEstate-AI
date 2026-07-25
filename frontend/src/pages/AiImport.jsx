import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// AI-assisted data entry — works for a SINGLE pdf or a BULK batch.
// Flow: upload PDFs → assign each to a project + title → extract (draft, nothing
// saved) → review/edit each → Save & Index. One button now does BOTH: writes the
// structured data to the project AND (optionally) files the same PDF as a
// searchable brochure. That folds in the old separate "Upload Brochure" tab.
export default function AiImport() {
  const [projects, setProjects] = useState([]);
  const [items, setItems] = useState([]); // {id, file, name, title, index, projectId, draft, status, error, open}
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.projects().then(setProjects); }, []);

  function addFiles(files) {
    const now = Date.now();
    const added = [...files].map((f, i) => ({
      id: `${now}-${i}`, file: f, name: f.name,
      // Sensible default title = the file name without its extension.
      title: (f.name || "").replace(/\.pdf$/i, ""),
      index: true,                      // also add the PDF to the searchable brochure library
      projectId: "",
      draft: null, status: "pending", error: null, open: false,
    }));
    setItems((prev) => [...prev, ...added]);
  }
  const patch = (id, upd) => setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...upd } : it)));
  const removeItem = (id) => setItems((prev) => prev.filter((it) => it.id !== id));

  async function extractOne(it) {
    patch(it.id, { status: "extracting", error: null });
    const fd = new FormData();
    fd.append("file", it.file);
    try {
      const r = await api.extractDraft(fd);
      patch(it.id, { status: "ready", draft: normalizeDraft(r.draft), open: true });
    } catch (err) {
      patch(it.id, { status: "error", error: err.message });
    }
  }

  async function extractAll() {
    setBusy(true);
    // sequential — avoids hammering the AI rate limit
    for (const it of items) {
      if (it.status === "pending") await extractOne(it);
    }
    setBusy(false);
  }

  async function saveOne(it) {
    if (!it.projectId) { patch(it.id, { error: "Choose a project first." }); return; }
    if (it.index && !it.title.trim()) { patch(it.id, { error: "Give the brochure a title (or turn off indexing)." }); return; }
    patch(it.id, { status: "saving", error: null });
    try {
      // 1) The structured data (towers, prices, amenities…) → the project.
      const r = await api.applyDraft(it.projectId, toPayload(it.draft));
      const s = r.applied;
      let savedMsg = `${s.fields} fields, ${s.towers} towers, ${s.configurations} configs, ${s.location_points} location, ${s.amenities} amenities${s.payment_plan ? ", plan" : ""}`;

      // 2) The same PDF → the searchable brochure library, so the assistant can
      //    quote it. Optional (checkbox). A failure here must not lose step 1.
      if (it.index) {
        try {
          const fd = new FormData();
          fd.append("project_id", it.projectId);
          fd.append("title", it.title.trim());
          fd.append("doc_type", "brochure");
          fd.append("file", it.file);
          const d = await api.uploadDocument(fd);
          savedMsg += ` · indexed (${d.chunks_indexed} chunks)`;
        } catch (err) {
          patch(it.id, { status: "saved", open: false, savedMsg,
            error: `Data saved, but indexing the PDF failed: ${err.message}. You can add it later from Documents.` });
          return;
        }
      }
      patch(it.id, { status: "saved", open: false, error: null, savedMsg });
    } catch (err) {
      patch(it.id, { status: "error", error: err.message });
    }
  }

  const pendingCount = items.filter((i) => i.status === "pending").length;

  return (
    <div className="admin-form">
      <div className="settings-note">
        🪄 Upload one or many brochure PDFs. Each is read by AI into an <b>editable draft</b> —
        assign it to a project, give it a title, review (especially prices), then <b>Save &amp; Index</b>.
        One step saves the extracted data <i>and</i> files the PDF as a searchable brochure.
        <b>Nothing is stored until you Save.</b>
      </div>

      <label className="field">
        <span>Add brochure PDF(s)</span>
        <input type="file" accept="application/pdf" multiple onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
      </label>

      {pendingCount > 0 && (
        <button type="button" className="btn btn-primary" onClick={extractAll} disabled={busy}>
          {busy ? "Extracting…" : `Extract all (${pendingCount})`}
        </button>
      )}

      <div className="import-queue">
        {items.map((it) => (
          <div className={`queue-item status-${it.status}`} key={it.id}>
            <div className="queue-row">
              <span className="queue-name">📄 {it.name}</span>
              <select value={it.projectId} onChange={(e) => patch(it.id, { projectId: e.target.value })} disabled={it.status === "saved"}>
                <option value="">Assign to project…</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input className="queue-title" value={it.title} disabled={it.status === "saved"}
                onChange={(e) => patch(it.id, { title: e.target.value })} placeholder="Brochure title…" />
              <StatusTag status={it.status} savedMsg={it.savedMsg} />
              <div className="queue-actions">
                {it.status === "pending" && <button className="btn btn-ghost" onClick={() => extractOne(it)}>Extract</button>}
                {(it.status === "ready" || it.status === "error") && it.draft && (
                  <button className="btn btn-ghost" onClick={() => patch(it.id, { open: !it.open })}>{it.open ? "Hide" : "Review"}</button>
                )}
                {it.status !== "saved" && <button className="btn btn-ghost" onClick={() => removeItem(it.id)}>✕</button>}
              </div>
            </div>
            {it.error && <div className="alert alert-error" style={{ margin: "6px 0" }}>{it.error}</div>}
            {it.open && it.draft && (
              <div className="queue-draft">
                <DraftEditor draft={it.draft} setDraft={(fn) => patch(it.id, { draft: typeof fn === "function" ? fn(it.draft) : fn })} />
                <label className="index-toggle" style={{ marginTop: 12 }}>
                  <input type="checkbox" checked={it.index}
                    onChange={(e) => patch(it.id, { index: e.target.checked })} />
                  <span>Also save this PDF as a searchable brochure (so the assistant can quote it)</span>
                </label>
                <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={() => saveOne(it)} disabled={it.status === "saving" || !it.projectId}>
                  {it.status === "saving" ? "Saving…" : (it.index ? "✓ Save & Index" : "✓ Save to project")}
                </button>
              </div>
            )}
          </div>
        ))}
        {items.length === 0 && <div className="muted" style={{ marginTop: 12 }}>No files yet. Add a PDF above.</div>}
      </div>
    </div>
  );
}

function StatusTag({ status, savedMsg }) {
  const map = {
    pending: ["chip-gray", "pending"], extracting: ["chip-amber", "extracting…"],
    ready: ["chip-amber", "review"], saving: ["chip-amber", "saving…"],
    saved: ["chip-green", "saved ✓"], error: ["chip-red", "error"],
  };
  const [cls, label] = map[status] || map.pending;
  return <span className={`status-chip ${cls}`} title={savedMsg || ""}>{label}</span>;
}

// The editable preview form for one draft.
function DraftEditor({ draft, setDraft }) {
  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  return (
    <div className="extract-preview">
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
        cols={[["type", "Type"], ["super_area", "Size", "number"], ["base_price", "Price", "number", true], ["plc", "PLC", "number"], ["gst_percent", "GST%", "number"]]}
        blank={{ type: "", super_area: "", base_price: "", price_unit: "per_sqft", plc: "", gst_percent: "" }} />

      <EditList title="Location & Connectivity" rows={draft.location_points} onChange={(rows) => setField("location_points", rows)}
        cols={[["category", "Category"], ["name", "Place"], ["distance", "Distance"]]}
        blank={{ category: "nearby", name: "", distance: "" }} />

      <EditList title="Amenities" rows={draft.amenities} onChange={(rows) => setField("amenities", rows)}
        cols={[["name", "Amenity"], ["category", "Category"]]}
        blank={{ name: "", category: "" }} />

      <div className="block-title" style={{ marginTop: 16 }}>Payment Plan</div>
      <label className="field" style={{ maxWidth: 260 }}><span>Plan name</span>
        <input value={draft.payment_plan?.name || ""} onChange={(e) => setField("payment_plan", { ...draft.payment_plan, name: e.target.value })} />
      </label>
      <EditList rows={draft.payment_plan?.milestones || []} onChange={(rows) => setField("payment_plan", { ...draft.payment_plan, milestones: rows })}
        cols={[["label", "Milestone"], ["percent", "%", "number"]]} blank={{ label: "", percent: "" }} />
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
    location_points: d.location_points || [],
    amenities: d.amenities || [],
    payment_plan: d.payment_plan || { name: "", milestones: [] },
  };
}

function toPayload(d) {
  const num = (v) => (v === "" || v == null ? null : Number(v));
  return {
    project_type: d.project_type || null, project_status: d.project_status || null,
    land_parcel: d.land_parcel || null, green_area: d.green_area || null,
    possession_date: d.possession_date || null,
    towers: d.towers.filter((t) => t.name).map((t) => ({ name: t.name, floors: num(t.floors), height: t.height || null, units_per_floor: num(t.units_per_floor) })),
    configurations: d.configurations.filter((c) => c.type).map((c) => ({
      type: c.type, super_area: num(c.super_area),
      base_price: num(c.base_price), price_unit: c.price_unit || "per_sqft", plc: num(c.plc), gst_percent: num(c.gst_percent),
    })),
    location_points: (d.location_points || []).filter((l) => l.name).map((l) => ({
      category: l.category || "nearby", name: l.name, distance: l.distance || null,
    })),
    amenities: (d.amenities || []).filter((a) => a.name).map((a) => ({
      name: a.name, category: a.category || null,
    })),
    payment_plan: d.payment_plan && d.payment_plan.milestones?.length
      ? { name: d.payment_plan.name || null, milestones: d.payment_plan.milestones.filter((m) => m.label).map((m) => ({ label: m.label, percent: Number(m.percent) || 0 })) }
      : null,
  };
}
