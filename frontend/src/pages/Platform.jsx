import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Super-admin only. Manage tenant organizations and subscription plans.
export default function Platform() {
  const [tab, setTab] = useState("orgs");
  const [pending, setPending] = useState(0);
  // Polled here rather than inside the tab, so the count is visible even while
  // you are on Plans or Alerts — a request you cannot see is a request missed.
  useEffect(() => {
    const load = () => api.saRequests().then((r) => setPending(r.length)).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [tab]);

  return (
    <div className="page">
      <div className="page-head">
        <h2>Platform</h2>
        <p className="muted">Manage companies (tenants), plans and your own alerts.</p>
      </div>
      <div className="calc-tabs">
        <button className={`tab ${tab === "orgs" ? "tab-active" : ""}`} onClick={() => setTab("orgs")}>
          Organizations{pending > 0 && <span className="tab-badge">{pending}</span>}
        </button>
        <button className={`tab ${tab === "plans" ? "tab-active" : ""}`} onClick={() => setTab("plans")}>Plans</button>
        <button className={`tab ${tab === "alerts" ? "tab-active" : ""}`} onClick={() => setTab("alerts")}>Alerts</button>
      </div>
      {tab === "orgs" && <Organizations />}
      {tab === "plans" && <Plans />}
      {tab === "alerts" && <PlatformAlerts />}
    </div>
  );
}

// Money walking towards you. Deliberately loud and at the top: the previous
// version of this was small amber text inside a table cell, which is not a
// notification — it is something you find only if you already knew to look.
function PendingRequests({ plans, onDone }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => api.saRequests().then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  if (!rows.length) return null;

  async function approve(r) {
    if (!confirm(`Move ${r.name} to ${r.requested_plan}? Their limits change immediately — record the payment separately.`)) return;
    setBusy(true);
    try { await api.saSetSubscription(r.organization_id, { plan_id: r.requested_plan_id }); load(); onDone(); }
    finally { setBusy(false); }
  }
  async function dismiss(r) {
    if (!confirm(`Dismiss ${r.name}'s request for ${r.requested_plan}? Their plan stays exactly as it is.`)) return;
    setBusy(true);
    try { await api.saSetSubscription(r.organization_id, { clear_request: true }); load(); onDone(); }
    finally { setBusy(false); }
  }

  return (
    <div className="req-box">
      <div className="req-head">
        💰 {rows.length} plan-change request{rows.length === 1 ? "" : "s"} waiting
      </div>
      {rows.map((r) => (
        <div key={r.organization_id} className="req-row">
          <div>
            <b>{r.name}</b> wants <b>{r.current_plan || "—"} → {r.requested_plan}</b>
            <div className="muted small">
              asked {r.requested_at ? new Date(r.requested_at).toLocaleString() : "—"}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-sm btn-primary" disabled={busy} onClick={() => approve(r)}>
              Switch to {r.requested_plan}
            </button>
            <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => dismiss(r)}>
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// Where the platform owner's own alerts go. Separate from a tenant's notify
// config — that one pings THEIR sales team, this one pings us.
function PlatformAlerts() {
  const [provider, setProvider] = useState("off");
  const [cfg, setCfg] = useState({});
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setCfg((s) => ({ ...s, [k]: v }));

  useEffect(() => {
    api.saNotifyConfig().then((r) => { setProvider(r.provider || "off"); setCfg(r.config || {}); }).catch(() => {});
  }, []);

  async function save() {
    setBusy(true); setMsg(null);
    try { await api.saSetNotifyConfig(provider, cfg); setMsg({ ok: true, text: "Saved." }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }
  async function test() {
    setBusy(true); setMsg(null);
    try { await api.saTestNotify(); setMsg({ ok: true, text: "Test sent ✓ check your Telegram/webhook." }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }

  return (
    <div className="admin-form">
      <div className="settings-note">
        <b>🔔 Your alerts as the platform owner.</b> Get pinged when a tenant asks to change plan, so
        you don't have to watch this page. This is <b>separate</b> from a tenant's own notification
        settings — those ping their sales team about website visitors.
        <br /><br />
        The list on <b>Organizations</b> is always correct on its own; this is just the nudge.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="tier-limits-box">
        <label className="field" style={{ maxWidth: 320 }}><span>Notify via</span>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="off">Off</option>
            <option value="telegram">Telegram (recommended)</option>
            <option value="webhook">Webhook (WhatsApp / any HTTP)</option>
          </select>
        </label>

        {provider === "telegram" && (
          <div className="calc-fields">
            <label className="field"><span>Bot token</span>
              <input value={cfg.bot_token || ""} onChange={(e) => set("bot_token", e.target.value)} placeholder="123456:ABC-DEF…" />
            </label>
            <label className="field"><span>Chat ID</span>
              <input value={cfg.chat_id || ""} onChange={(e) => set("chat_id", e.target.value)} placeholder="-1001234567890 or your user id" />
            </label>
            <p className="muted small" style={{ gridColumn: "1 / -1", margin: 0 }}>
              Create a bot with <b>@BotFather</b>, message it once, then get your chat id from <b>@getidsbot</b>.
              Use a private chat or a group only you and your team can see — plan requests name your customers.
            </p>
          </div>
        )}

        {provider === "webhook" && (
          <>
            <label className="field"><span>Webhook URL</span>
              <input value={cfg.url || ""} onChange={(e) => set("url", e.target.value)} placeholder="https://your-service.com/send" />
            </label>
            <label className="field"><span>Body template (JSON, use <code>{"{{text}}"}</code>)</span>
              <textarea rows={3} value={cfg.body_template || ""} onChange={(e) => set("body_template", e.target.value)}
                placeholder='{"text": "{{text}}"}' />
            </label>
          </>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "…" : "Save"}</button>
          {provider !== "off" && <button className="btn" onClick={test} disabled={busy}>Send test</button>}
        </div>
      </div>
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

// Onboarding: a new tenant whose assistant knows nothing is a bad first day.
// Copies projects WITH their prices, plans and amenities (same pack code as the
// file export), so the new company can answer questions straight away.
function SeedProjects({ orgs, onDone }) {
  const [target, setTarget] = useState("");
  const [source, setSource] = useState("");
  const [projects, setProjects] = useState([]);
  const [picked, setPicked] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    setProjects([]); setPicked([]);
    if (!source) return;
    api.saOrgProjects(source).then(setProjects).catch(() => setProjects([]));
  }, [source]);

  const toggle = (id) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  async function seed() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.saSeedProjects(Number(target), Number(source), picked.length ? picked : null);
      setMsg({
        ok: true,
        text: `Copied ${r.created} project${r.created === 1 ? "" : "s"}.`
          + (r.skipped_existing ? ` ${r.skipped_existing} were already there.` : "")
          + (r.errors.length ? ` Problems: ${r.errors.join("; ")}` : ""),
      });
      setPicked([]);
      onDone();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }

  return (
    <details className="seed-box">
      <summary>🌱 Give a company a starter set of projects</summary>
      <p className="muted small" style={{ margin: "8px 0 12px" }}>
        Copies projects <b>with</b> their configurations, prices, payment plans, towers and amenities —
        so a newly onboarded company's assistant can answer from day one. Projects it already has
        (same slug) are skipped. Brochures are not copied.
      </p>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="calc-fields">
        <label className="field"><span>Copy from</span>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Select a company…</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
        <label className="field"><span>Into</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Select a company…</option>
            {orgs.filter((o) => String(o.id) !== String(source))
              .map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
      </div>

      {source && (
        <div className="seed-list">
          <div className="muted small" style={{ marginBottom: 6 }}>
            {projects.length ? "Tick the ones to copy — none ticked means all." : "That company has no projects."}
          </div>
          {projects.map((p) => (
            <label key={p.id} className="seed-item">
              <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} />
              <span><b>{p.name}</b> <span className="muted small">
                {p.city || "—"} · {p.configurations} configs · {p.amenities} amenities
              </span></span>
            </label>
          ))}
        </div>
      )}

      <button className="btn btn-primary" style={{ marginTop: 10 }}
        disabled={busy || !source || !target} onClick={seed}>
        {busy ? "Copying…" : picked.length ? `Copy ${picked.length} project(s)` : "Copy all projects"}
      </button>
    </details>
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

      <PendingRequests plans={plans} onDone={load} />
      <SeedProjects orgs={orgs} onDone={load} />

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
