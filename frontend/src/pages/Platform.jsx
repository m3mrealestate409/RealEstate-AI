import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Super-admin only. Manage tenant organizations and subscription plans.
export default function Platform() {
  const [tab, setTab] = useState("orgs");
  return (
    <div className="page">
      <div className="page-head">
        <h2>Platform</h2>
        <p className="muted">Manage companies (tenants) and subscription plans.</p>
      </div>
      <div className="calc-tabs">
        <button className={`tab ${tab === "orgs" ? "tab-active" : ""}`} onClick={() => setTab("orgs")}>Organizations</button>
        <button className={`tab ${tab === "plans" ? "tab-active" : ""}`} onClick={() => setTab("plans")}>Plans</button>
      </div>
      {tab === "orgs" ? <Organizations /> : <Plans />}
    </div>
  );
}

// Effective billing state. `past_due` is the one that needs chasing — it is
// still serving, but on borrowed time.
const BILLING_CHIP = {
  active: ["chip-green", "active"],
  trialing: ["chip-blue", "trial"],
  past_due: ["chip-amber", "past due"],
  suspended: ["chip-red", "suspended"],
  cancelled: ["chip-gray", "cancelled"],
  none: ["chip-gray", "—"],
};

function BillingChip({ o }) {
  const [cls, label] = BILLING_CHIP[o.status] || BILLING_CHIP.none;
  const d = o.days_left;
  return (
    <>
      <span className={`status-chip ${cls}`}>{label}</span>
      {d != null && (
        <div className="muted small" style={{ marginTop: 3 }}>
          {d >= 0 ? `${d} day${d === 1 ? "" : "s"} left` : `${Math.abs(d)} day${d === -1 ? "" : "s"} over`}
        </div>
      )}
      {o.note && <div className="muted small" title={o.note}>{o.note.slice(0, 28)}</div>}
      {o.requested_plan && (
        <div className="muted small" style={{ marginTop: 3, color: "var(--amber)", fontWeight: 700 }}
          title="This tenant asked to change plan — switch the Plan dropdown to action it.">
          ↗ wants {o.requested_plan}
        </div>
      )}
    </>
  );
}

// The whole Phase-1 payment flow: someone paid, so record how far it covers —
// and record the money itself, which `paid_till` alone would lose on renewal.
function PaidTill({ o, onDone, onErr }) {
  const [date, setDate] = useState((o.expires_at || "").slice(0, 10));
  const [note, setNote] = useState(o.note || "");
  const [amount, setAmount] = useState(o.price_monthly ?? "");
  const [method, setMethod] = useState("upi");
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);

  async function markPaid() {
    if (!date) return;
    setBusy(true);
    try {
      const r = await api.saSetSubscription(o.id, {
        paid_till: date, note, method, reference: ref,
        amount: amount === "" ? null : Number(amount),
      });
      setRef("");
      onDone();
      if (r.payment) onErr(null, `Recorded ${r.payment.receipt_no} — ₹${r.payment.amount.toLocaleString("en-IN")}`);
    } catch (e) { onErr(e.message); }
    finally { setBusy(false); }
  }
  async function setStatus(status) {
    const warn = status === "suspended"
      ? `Suspend ${o.name}? AI answers stop immediately. Their data, logins and leads stay untouched.`
      : `Start a fresh 14-day trial for ${o.name}?`;
    if (!confirm(warn)) return;
    setBusy(true);
    try {
      await api.saSetSubscription(o.id, status === "trialing" ? { trial_days: 14 } : { status });
      onDone();
    } catch (e) { onErr(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="bill-cell">
      <input type="date" value={date} onChange={(e) => setDate(e.target.value)} title="Paid up to" />
      <div className="bill-actions">
        <input type="number" min="0" step="1" placeholder="amount" value={amount}
          onChange={(e) => setAmount(e.target.value)} style={{ width: 78 }} title="Amount received" />
        <select value={method} onChange={(e) => setMethod(e.target.value)} title="How it was paid">
          <option value="upi">UPI</option><option value="bank">Bank</option>
          <option value="cash">Cash</option><option value="card">Card</option>
          <option value="other">Other</option>
        </select>
      </div>
      <input placeholder="UPI ref / UTR" value={ref} onChange={(e) => setRef(e.target.value)} />
      <input placeholder="note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="bill-actions">
        <button className="btn btn-sm btn-primary" onClick={markPaid} disabled={busy || !date}>
          {busy ? "…" : "Mark paid"}
        </button>
        {o.status === "suspended"
          ? <button className="btn btn-sm" onClick={() => setStatus("trialing")} disabled={busy}>Trial</button>
          : <button className="btn btn-sm btn-ghost btn-danger" onClick={() => setStatus("suspended")} disabled={busy}>Suspend</button>}
      </div>
    </div>
  );
}

function Organizations() {
  const [orgs, setOrgs] = useState([]);
  const [plans, setPlans] = useState([]);
  const [msg, setMsg] = useState(null);
  const [f, setF] = useState({ name: "", slug: "", plan_id: "", admin_email: "", admin_password: "", admin_name: "" });
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const load = () => { api.saOrgs().then(setOrgs); api.saPlans().then(setPlans); };
  useEffect(() => { load(); }, []);

  async function createOrg(e) {
    e.preventDefault(); setMsg(null);
    try {
      await api.saCreateOrg({ ...f, plan_id: Number(f.plan_id) });
      setF({ name: "", slug: "", plan_id: "", admin_email: "", admin_password: "", admin_name: "" });
      load(); setMsg({ ok: true, text: "Company created with its admin." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }
  // Goes through the subscription, not saUpdateOrg: that keeps the org's plan
  // and its subscription in step, and answers any pending upgrade request.
  async function changePlan(id, plan_id) {
    try { await api.saSetSubscription(id, { plan_id: Number(plan_id) }); load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  async function toggleActive(o) {
    await api.saUpdateOrg(o.id, { is_active: !o.is_active }); load();
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="settings-note">
        <b>Billing is recorded by hand.</b> Money arrives by bank transfer or UPI; you enter the date it
        is paid up to. An expired org keeps working for <b>{orgs[0]?.grace_days ?? 7} days</b> (grace), then
        AI answers stop — logins, data and leads are never withheld.
      </div>

      <div className="table-wrap" style={{ marginBottom: 20 }}>
        <table className="data-table">
          <thead><tr>
            <th>Company</th><th>Plan</th><th>Employees</th><th>Queries today</th>
            <th>Billing</th><th>Paid till</th><th>Access</th>
          </tr></thead>
          <tbody>
            {orgs.map((o) => (
              <tr key={o.id}>
                <td><b>{o.name}</b><div className="muted small">{o.slug}</div></td>
                <td>
                  <select value={o.plan_id || ""} onChange={(e) => changePlan(o.id, e.target.value)}>
                    {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </td>
                <td>{o.employees} / {o.max_employees}</td>
                <td>{o.queries_today} / {o.daily_llm_quota}</td>
                <td><BillingChip o={o} /></td>
                <td>
                  <PaidTill o={o} onDone={load}
                    onErr={(err, ok) => setMsg(err ? { ok: false, text: err } : { ok: true, text: ok })} />
                </td>
                <td>
                  <button className={`status-chip ${o.is_active ? "chip-green" : "chip-gray"}`}
                    onClick={() => toggleActive(o)} style={{ cursor: "pointer", border: "none" }}
                    title="Disable the whole account (separate from billing)">
                    {o.is_active ? "enabled" : "disabled"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="block-title">Add a company (tenant)</div>
      <form onSubmit={createOrg}>
        <div className="calc-fields">
          <label className="field"><span>Company name</span><input value={f.name} onChange={(e) => set("name", e.target.value)} required /></label>
          <label className="field"><span>Slug (unique)</span><input value={f.slug} onChange={(e) => set("slug", e.target.value)} required /></label>
          <label className="field"><span>Plan</span>
            <select value={f.plan_id} onChange={(e) => set("plan_id", e.target.value)} required>
              <option value="">Select…</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.max_employees} emp · {p.daily_llm_quota} q/day)</option>)}
            </select>
          </label>
          <label className="field"><span>Admin name</span><input value={f.admin_name} onChange={(e) => set("admin_name", e.target.value)} /></label>
          <label className="field"><span>Admin email</span><input type="email" value={f.admin_email} onChange={(e) => set("admin_email", e.target.value)} required /></label>
          <label className="field"><span>Admin password</span><input type="password" value={f.admin_password} onChange={(e) => set("admin_password", e.target.value)} required /></label>
        </div>
        <button className="btn btn-primary">Create company</button>
      </form>
    </div>
  );
}

function Plans() {
  const [plans, setPlans] = useState([]);
  const [msg, setMsg] = useState(null);
  const [nf, setNf] = useState({ name: "", max_employees: 5, daily_llm_quota: 25, price_monthly: 0 });
  const load = () => api.saPlans().then(setPlans);
  useEffect(() => { load(); }, []);

  async function saveField(id, field, value) {
    await api.saUpdatePlan(id, { [field]: Number(value) }); load();
  }
  async function createPlan(e) {
    e.preventDefault(); setMsg(null);
    try {
      await api.saCreatePlan({ ...nf, max_employees: Number(nf.max_employees), daily_llm_quota: Number(nf.daily_llm_quota), price_monthly: Number(nf.price_monthly) });
      setNf({ name: "", max_employees: 5, daily_llm_quota: 25, price_monthly: 0 });
      load(); setMsg({ ok: true, text: "Plan created." });
    } catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      <div className="table-wrap" style={{ marginBottom: 20 }}>
        <table className="data-table">
          <thead><tr><th>Plan</th><th>Max employees</th><th>Daily query quota</th><th>Price/mo (₹)</th><th>Companies</th></tr></thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.id}>
                <td><b>{p.name}</b></td>
                <td><EditNum value={p.max_employees} onSave={(v) => saveField(p.id, "max_employees", v)} /></td>
                <td><EditNum value={p.daily_llm_quota} onSave={(v) => saveField(p.id, "daily_llm_quota", v)} /></td>
                <td><EditNum value={p.price_monthly} onSave={(v) => saveField(p.id, "price_monthly", v)} /></td>
                <td>{p.organizations}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="block-title">Add a plan</div>
      <form onSubmit={createPlan}>
        <div className="calc-fields">
          <label className="field"><span>Name</span><input value={nf.name} onChange={(e) => setNf({ ...nf, name: e.target.value })} required /></label>
          <label className="field"><span>Max employees</span><input type="number" value={nf.max_employees} onChange={(e) => setNf({ ...nf, max_employees: e.target.value })} /></label>
          <label className="field"><span>Daily query quota</span><input type="number" value={nf.daily_llm_quota} onChange={(e) => setNf({ ...nf, daily_llm_quota: e.target.value })} /></label>
          <label className="field"><span>Price/mo (₹)</span><input type="number" value={nf.price_monthly} onChange={(e) => setNf({ ...nf, price_monthly: e.target.value })} /></label>
        </div>
        <button className="btn btn-primary">Create plan</button>
      </form>
    </div>
  );
}

// Inline-editable number cell (saves on blur / Enter when changed).
function EditNum({ value, onSave }) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  const changed = String(v) !== String(value);
  return (
    <span className="ecr-inline">
      <input type="number" value={v} style={{ width: 90 }}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && changed) onSave(v); }} />
      {changed && <button type="button" className="btn btn-primary" onClick={() => onSave(v)}>Save</button>}
    </span>
  );
}
