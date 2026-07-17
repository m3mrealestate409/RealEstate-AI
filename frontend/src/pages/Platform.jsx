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

// Recording a payment is a small form, not a table cell. It used to be five
// inputs stacked inside one column, which read as clutter and made a careful
// job — money — feel careless. A dialog gives it room and a single Save.
function PaymentDialog({ o, onClose, onDone, onErr }) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState((o.expires_at || "").slice(0, 10) || today);
  const [amount, setAmount] = useState(o.price_monthly ?? "");
  const [method, setMethod] = useState("upi");
  const [ref, setRef] = useState("");
  const [note, setNote] = useState(o.note || "");
  const [busy, setBusy] = useState(false);

  // Esc closes — a dialog you can only leave by aiming at an X is a trap.
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);

  async function save() {
    if (!date) return;
    setBusy(true);
    try {
      const r = await api.saSetSubscription(o.id, {
        paid_till: date, note, method, reference: ref,
        amount: amount === "" ? null : Number(amount),
      });
      onDone();
      onClose();
      if (r.payment) {
        onErr(null, `Recorded ${r.payment.receipt_no} — ₹${r.payment.amount.toLocaleString("en-IN")} from ${o.name}.`);
      }
    } catch (e) { onErr(e.message); setBusy(false); }
  }

  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-label={`Record a payment from ${o.name}`}>
        <div className="modal-head">
          <div>
            <div className="modal-title">Record a payment</div>
            <div className="muted small">{o.name} · {o.plan || "—"}</div>
          </div>
          <button className="modal-x" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="modal-body">
          <div className="calc-fields">
            <label className="field"><span>Paid up to</span>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label className="field"><span>Amount received (₹)</span>
              <input type="number" min="0" step="1" value={amount} onChange={(e) => setAmount(e.target.value)}
                placeholder={String(o.price_monthly ?? 0)} />
            </label>
            <label className="field"><span>How they paid</span>
              <select value={method} onChange={(e) => setMethod(e.target.value)}>
                <option value="upi">UPI</option><option value="bank">Bank transfer</option>
                <option value="cash">Cash</option><option value="card">Card</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="field"><span>Reference (UPI ref / UTR)</span>
              <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="optional" />
            </label>
          </div>
          <label className="field"><span>Note</span>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="optional — e.g. August invoice" />
          </label>
          <div className="conn-hint">
            This creates a receipt the customer can download, and extends their access to the date above.
          </div>
        </div>

        <div className="modal-foot">
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={busy || !date}>
            {busy ? "Saving…" : "Record payment"}
          </button>
        </div>
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
  const [paying, setPaying] = useState(null);   // the org whose payment dialog is open
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
    const warn = o.is_active
      ? `Disable ${o.name} entirely? Nobody there will be able to log in. This is separate from billing — to only stop AI answers, use Suspend.`
      : `Re-enable ${o.name}? Their logins start working again.`;
    if (!confirm(warn)) return;
    try { await api.saUpdateOrg(o.id, { is_active: !o.is_active }); load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  async function setStatus(o, status) {
    const warn = status === "suspended"
      ? `Suspend ${o.name}? AI answers stop immediately. Their data, logins and leads stay untouched.`
      : `Start a fresh 14-day trial for ${o.name}?`;
    if (!confirm(warn)) return;
    try {
      await api.saSetSubscription(o.id, status === "trialing" ? { trial_days: 14 } : { status });
      load();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  }

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <PendingRequests plans={plans} onDone={load} />
      <SeedProjects orgs={orgs} onDone={load} />

      <StatTiles orgs={orgs} />

      <div className="pf-hint">
        Billing is recorded by hand — money arrives by bank transfer or UPI, you enter the date it's
        paid up to. An expired company keeps working for <b>{orgs[0]?.grace_days ?? 7} days</b>, then AI
        answers stop. Logins, data and leads are never withheld.
      </div>

      <div className="tenant-grid">
        {orgs.map((o) => (
          <TenantCard key={o.id} o={o} plans={plans}
            onPlan={(v) => changePlan(o.id, v)}
            onToggle={() => toggleActive(o)}
            onPay={() => setPaying(o)}
            onStatus={(s) => setStatus(o, s)} />
        ))}
        {orgs.length === 0 && <div className="muted">No companies yet.</div>}
      </div>

      <details className="seed-box" style={{ marginTop: 18 }}>
        <summary>➕ Add a company (tenant)</summary>
        <p className="muted small" style={{ margin: "8px 0 12px" }}>
          Creates the company and its one admin account. They start on a 14-day trial — record a
          payment to put them on a paid period. Give them a starter set of projects above so their
          assistant isn't empty on day one.
        </p>
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
      </details>

      {paying && (
        <PaymentDialog o={paying} onClose={() => setPaying(null)} onDone={load}
          onErr={(err, ok) => setMsg(err ? { ok: false, text: err } : { ok: true, text: ok })} />
      )}
    </div>
  );
}

const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");

// The four numbers you'd want if someone asked "how's the business?" — and the
// one that matters most, money at risk, sits where you can't miss it.
function StatTiles({ orgs }) {
  const active = orgs.filter((o) => o.status === "active").length;
  const trial = orgs.filter((o) => o.status === "trialing").length;
  const risk = orgs.filter((o) => ["past_due", "suspended"].includes(o.status));
  const mrr = orgs
    .filter((o) => o.status === "active")
    .reduce((s, o) => s + (o.price_monthly || 0), 0);
  const riskMrr = risk.reduce((s, o) => s + (o.price_monthly || 0), 0);

  return (
    <div className="pf-stats">
      <div className="pf-stat">
        <div className="pf-stat-v">{orgs.length}</div>
        <div className="pf-stat-l">Companies</div>
      </div>
      <div className="pf-stat">
        <div className="pf-stat-v">{active}<span className="pf-stat-sub">{trial ? ` +${trial} trial` : ""}</span></div>
        <div className="pf-stat-l">Paid &amp; active</div>
      </div>
      <div className={`pf-stat ${risk.length ? "pf-stat-risk" : ""}`}>
        <div className="pf-stat-v">{risk.length}</div>
        <div className="pf-stat-l">
          Needs chasing{risk.length ? ` · ${inr(riskMrr)} at risk` : ""}
        </div>
      </div>
      <div className="pf-stat pf-stat-hero">
        <div className="pf-stat-v">{inr(mrr)}</div>
        <div className="pf-stat-l">Monthly recurring</div>
      </div>
    </div>
  );
}

function Meter({ used, cap, label }) {
  const pct = cap ? Math.min(100, Math.round((used / cap) * 100)) : 0;
  return (
    <div className="tc-meter">
      <div className="tc-meter-top">
        <span className="muted small">{label}</span>
        <span className="tc-meter-n">{used}<span className="muted"> / {cap ?? "∞"}</span></span>
      </div>
      <div className={`bill-bar ${pct > 80 ? "bill-bar-warn" : ""}`}><span style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function TenantCard({ o, plans, onPlan, onToggle, onPay, onStatus }) {
  const [cls, label] = BILLING_CHIP[o.status] || BILLING_CHIP.none;
  const d = o.days_left;
  const paidTill = o.expires_at
    ? new Date(o.expires_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
    : null;

  return (
    <div className={`tenant-card ${["past_due", "suspended"].includes(o.status) ? "tenant-card-risk" : ""}`}>
      <div className="tc-head">
        <div className="tc-avatar">{(o.name || "?")[0].toUpperCase()}</div>
        <div className="tc-id">
          <div className="tc-name">{o.name}</div>
          <div className="muted small">{o.slug}</div>
        </div>
        <span className={`status-chip ${cls}`}>{label}</span>
      </div>

      {o.requested_plan && (
        <div className="tc-flag">↗ Asked to move to <b>{o.requested_plan}</b></div>
      )}

      <div className="tc-meters">
        <Meter used={o.employees} cap={o.max_employees} label="Employees" />
        <Meter used={o.queries_today} cap={o.daily_llm_quota} label="AI questions today" />
      </div>

      <div className="tc-row">
        <span className="muted small">Plan</span>
        <select className="tc-plan" value={o.plan_id || ""} onChange={(e) => onPlan(e.target.value)}>
          {plans.map((p) => <option key={p.id} value={p.id}>{p.name} — {inr(p.price_monthly)}/mo</option>)}
        </select>
      </div>

      <div className="tc-row">
        <span className="muted small">Paid till</span>
        <span className="tc-paid">
          {paidTill || "—"}
          {d != null && (
            <span className={`muted small ${d < 0 ? "tc-over" : ""}`}>
              {d >= 0 ? ` · ${d}d left` : ` · ${Math.abs(d)}d over`}
            </span>
          )}
        </span>
      </div>

      {o.note && <div className="tc-note" title={o.note}>{o.note}</div>}

      <div className="tc-actions">
        <button className="btn btn-sm btn-primary" onClick={onPay}>💰 Record payment</button>
        {o.status === "suspended"
          ? <button className="btn btn-sm" onClick={() => onStatus("trialing")}>Start trial</button>
          : <button className="btn btn-sm btn-ghost btn-danger" onClick={() => onStatus("suspended")}>Suspend</button>}
        <button className={`btn btn-sm btn-ghost tc-access ${o.is_active ? "" : "tc-off"}`}
          onClick={onToggle}
          title="Disable the whole account — separate from billing">
          {o.is_active ? "Enabled" : "Disabled"}
        </button>
      </div>
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

  async function toggleActive(p) {
    const warn = p.is_active
      ? `Hide ${p.name} from the pricing page? Companies already on it keep everything — it just stops being offered.`
      : `Offer ${p.name} again? It reappears on every customer's Pricing page.`;
    if (!confirm(warn)) return;
    try { await api.saUpdatePlan(p.id, { is_active: !p.is_active }); load(); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
  }

  const mrr = plans.reduce((s, p) => s + (p.price_monthly || 0) * (p.organizations || 0), 0);

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="settings-note">
        <b>💎 This is where your pricing lives.</b> Change a price and it applies to that plan
        everywhere — the customer's Pricing page, and the amount pre-filled when you record their next
        payment. It never re-charges anyone or touches money already recorded.
      </div>

      <div className="plan-grid">
        {plans.map((p) => (
          <div key={p.id} className={`plan-card ${p.is_active ? "" : "plan-card-off"}`}>
            <div className="plan-card-head">
              <div className="plan-card-name">{p.name}</div>
              <button className={`status-chip ${p.is_active ? "chip-green" : "chip-gray"} plan-toggle`}
                onClick={() => toggleActive(p)}
                title={p.is_active ? "Offered to customers — click to hide" : "Hidden from customers — click to offer"}>
                {p.is_active ? "offered" : "hidden"}
              </button>
            </div>

            <div className="plan-price">
              <span className="plan-cur">₹</span>
              <EditNum value={p.price_monthly} onSave={(v) => saveField(p.id, "price_monthly", v)} big />
              <span className="plan-per">/month</span>
            </div>

            <div className="plan-rows">
              <div className="plan-row">
                <span className="muted small">Max employees</span>
                <EditNum value={p.max_employees} onSave={(v) => saveField(p.id, "max_employees", v)} />
              </div>
              <div className="plan-row">
                <span className="muted small">AI questions / day</span>
                <EditNum value={p.daily_llm_quota} onSave={(v) => saveField(p.id, "daily_llm_quota", v)} />
              </div>
            </div>

            <div className="plan-foot">
              <span><b>{p.organizations}</b> compan{p.organizations === 1 ? "y" : "ies"}</span>
              {p.organizations > 0 && p.price_monthly > 0 && (
                <span className="muted">{inr(p.price_monthly * p.organizations)}/mo</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {mrr > 0 && (
        <div className="pf-hint" style={{ marginTop: 12 }}>
          These plans bring in <b>{inr(mrr)}</b> a month across {plans.reduce((s, p) => s + (p.organizations || 0), 0)} companies.
          Editing a price changes what they're billed <i>next</i> time — past receipts keep the amount they were paid at.
        </div>
      )}

      <details className="seed-box" style={{ marginTop: 16 }}>
        <summary>➕ Add a plan</summary>
        <form onSubmit={createPlan} style={{ marginTop: 10 }}>
          <div className="calc-fields">
            <label className="field"><span>Name</span><input value={nf.name} onChange={(e) => setNf({ ...nf, name: e.target.value })} required /></label>
            <label className="field"><span>Max employees</span><input type="number" value={nf.max_employees} onChange={(e) => setNf({ ...nf, max_employees: e.target.value })} /></label>
            <label className="field"><span>AI questions / day</span><input type="number" value={nf.daily_llm_quota} onChange={(e) => setNf({ ...nf, daily_llm_quota: e.target.value })} /></label>
            <label className="field"><span>Price / month (₹)</span><input type="number" value={nf.price_monthly} onChange={(e) => setNf({ ...nf, price_monthly: e.target.value })} /></label>
          </div>
          <button className="btn btn-primary">Create plan</button>
        </form>
      </details>
    </div>
  );
}

// Inline-editable number (saves on Enter, or via the Save button that appears
// once it differs — so a stray keystroke never silently reprices a plan).
function EditNum({ value, onSave, big = false }) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  const changed = String(v) !== String(value);
  return (
    <span className={`ecr-inline ${big ? "editnum-big" : ""}`}>
      <input type="number" value={v} style={big ? undefined : { width: 90 }}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && changed) onSave(v); }} />
      {changed && <button type="button" className="btn btn-sm btn-primary" onClick={() => onSave(v)}>Save</button>}
    </span>
  );
}
