import { useEffect, useState } from "react";
import { api, downloadFile, openBlobTab } from "../api/client.js";

// Billing lives in the sidebar, not under Admin: an admin checks their plan,
// usage and invoices far more often than they edit doc types — and "what am I
// paying for" is not an administration task, it is its own job.

const BILL_LABEL = {
  active: ["chip-green", "Active"],
  trialing: ["chip-blue", "Trial"],
  past_due: ["chip-amber", "Payment due"],
  suspended: ["chip-red", "Suspended"],
  cancelled: ["chip-gray", "Cancelled"],
  none: ["chip-gray", "—"],
};

// Shown to an org admin above every Admin page while billing needs attention.
// Silent when all is well — a banner that is always there stops being read.
export function BillingBanner() {
  const [b, setB] = useState(null);
  useEffect(() => { api.myBilling().then(setB).catch(() => {}); }, []);
  if (!b || !["past_due", "suspended", "cancelled"].includes(b.status)) return null;
  const due = b.status === "past_due";
  return (
    <div className={`alert ${due ? "alert-warn" : "alert-error"}`} style={{ marginBottom: 14 }}>
      {due ? (
        <>
          <b>Your subscription has lapsed.</b> Everything still works for now, but AI answers will pause
          in {(b.grace_days ?? 7) + (b.days_left ?? 0)} day(s). Please settle the invoice to avoid interruption.
        </>
      ) : (
        <><b>AI answers are paused</b> — your subscription is {b.status}. Your data and leads are safe and
          nothing has been deleted. Renew to switch answers back on.</>
      )}
    </div>
  );
}

function PlanUsage() {
  const [b, setB] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.myBilling().then(setB).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="alert alert-error">{err}</div>;
  if (!b) return <div className="muted">Loading…</div>;

  const [cls, label] = BILL_LABEL[b.status] || BILL_LABEL.none;
  const pct = (used, cap) => (cap ? Math.min(100, Math.round((used / cap) * 100)) : 0);
  const qPct = pct(b.queries_today, b.daily_llm_quota);
  const ePct = pct(b.employees, b.max_employees);
  const expiry = b.expires_at ? new Date(b.expires_at).toLocaleDateString(undefined,
    { day: "numeric", month: "short", year: "numeric" }) : null;

  return (
    <div className="admin-form">
      <div className="settings-note">
        <b>💳 Your plan.</b> What your subscription includes and how much of it you have used today.
        To change plans or settle an invoice, contact us — we will update it here.
      </div>

      <div className="tier-limits-box">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div style={{ fontSize: 20, fontWeight: 800 }}>{b.plan || "—"}</div>
          <span className={`status-chip ${cls}`}>{label}</span>
          {b.price_monthly ? <span className="muted">₹{b.price_monthly.toLocaleString("en-IN")}/month</span> : null}
        </div>
        {expiry && (
          <div className="muted small" style={{ marginTop: 6 }}>
            {b.status === "trialing" ? "Trial ends" : "Paid till"} <b>{expiry}</b>
            {b.days_left != null && (b.days_left >= 0
              ? ` · ${b.days_left} day${b.days_left === 1 ? "" : "s"} left`
              : ` · ${Math.abs(b.days_left)} day${b.days_left === -1 ? "" : "s"} overdue`)}
          </div>
        )}
        {b.last_payment && (
          <div className="muted small" style={{ marginTop: 4 }}>
            Last payment <b>{inr(b.last_payment.amount)}</b> on {onDate(b.last_payment.paid_on)}
            {b.last_payment.reference ? ` · ref ${b.last_payment.reference}` : ""}
          </div>
        )}
        {b.requested_plan && (
          <div className="muted small" style={{ marginTop: 4 }}>
            You've asked to move to <b>{b.requested_plan}</b> — we'll be in touch.
          </div>
        )}
        {b.reason && <div className="alert alert-error" style={{ marginTop: 10 }}>{b.reason}</div>}
      </div>

      <div className="bill-grid">
        <div className="bill-stat">
          <div className="bill-stat-v">{b.queries_today} <span className="muted" style={{ fontSize: 14 }}>/ {b.daily_llm_quota ?? "∞"}</span></div>
          <div className="bill-stat-l">AI questions today</div>
          {b.daily_llm_quota ? (
            <div className={`bill-bar ${qPct > 80 ? "bill-bar-warn" : ""}`}><span style={{ width: `${qPct}%` }} /></div>
          ) : null}
        </div>
        <div className="bill-stat">
          <div className="bill-stat-v">{b.employees} <span className="muted" style={{ fontSize: 14 }}>/ {b.max_employees ?? "∞"}</span></div>
          <div className="bill-stat-l">Employees</div>
          {b.max_employees ? (
            <div className={`bill-bar ${ePct > 80 ? "bill-bar-warn" : ""}`}><span style={{ width: `${ePct}%` }} /></div>
          ) : null}
        </div>
        <div className="bill-stat">
          <div className="bill-stat-v">{b.ai_enabled ? "On" : "Paused"}</div>
          <div className="bill-stat-l">AI answers</div>
        </div>
      </div>

      <div className="conn-hint">
        Only AI answers depend on the subscription. Price and inventory look-ups come straight from your
        own data and keep working — as do your logins, leads and Live Chat.
      </div>
    </div>
  );
}

const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");
const onDate = (s) => (s ? new Date(s).toLocaleDateString(undefined,
  { day: "numeric", month: "short", year: "numeric" }) : "—");

function Payments() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.myPayments().then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="alert alert-error">{err}</div>;
  if (!d) return <div className="muted">Loading…</div>;

  const last = d.payments[0];
  async function openReceipt(id) {
    setBusy(true);
    try { await openBlobTab(`/v1/billing/payments/${id}/receipt`); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  async function downloadCsv() {
    setBusy(true);
    try { await downloadFile("/v1/billing/payments.csv", "payments.csv"); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="admin-form">
      <div className="settings-note">
        <b>💰 Every payment we've received from you.</b> Open any row for a printable receipt, or
        download the lot as a spreadsheet for your accountant.
      </div>

      {last ? (
        <div className="tier-limits-box">
          <div className="block-title">Last transaction</div>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "baseline" }}>
            <div style={{ fontSize: 24, fontWeight: 800 }}>{inr(last.amount)}</div>
            <div className="muted">
              {last.plan} · {onDate(last.paid_on)} · {(last.method || "—").toUpperCase()}
              {last.reference ? ` · ref ${last.reference}` : ""}
            </div>
            <button className="btn btn-sm" disabled={busy} onClick={() => openReceipt(last.id)}>
              🧾 Receipt
            </button>
          </div>
          <div className="muted small" style={{ marginTop: 4 }}>
            Covers {onDate(last.period_start)} → {onDate(last.period_end)}
          </div>
        </div>
      ) : (
        <div className="tier-limits-box muted">
          No payments recorded yet. If you're on a trial, nothing is due until it ends.
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    margin: "16px 0 8px", flexWrap: "wrap", gap: 10 }}>
        <div className="block-title" style={{ margin: 0 }}>
          History · {d.count} payment{d.count === 1 ? "" : "s"} · {inr(d.total_paid)} total
        </div>
        {d.count > 0 && (
          <button className="btn btn-sm" disabled={busy} onClick={downloadCsv}>⬇️ Download CSV</button>
        )}
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead><tr>
            <th>Receipt</th><th>Paid on</th><th>Plan</th><th>Period</th>
            <th>Method</th><th>Amount</th><th></th>
          </tr></thead>
          <tbody>
            {d.payments.map((p) => (
              <tr key={p.id}>
                <td><code className="muted">{p.receipt_no}</code></td>
                <td>{onDate(p.paid_on)}</td>
                <td>{p.plan || "—"}</td>
                <td className="muted small">{onDate(p.period_start)} → {onDate(p.period_end)}</td>
                <td>
                  {(p.method || "—").toUpperCase()}
                  {p.reference && <div className="muted small">{p.reference}</div>}
                </td>
                <td><b>{inr(p.amount)}</b></td>
                <td>
                  <button className="btn btn-sm btn-ghost" disabled={busy}
                    onClick={() => openReceipt(p.id)}>Receipt</button>
                </td>
              </tr>
            ))}
            {d.count === 0 && <tr><td colSpan="7" className="muted">Nothing yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="conn-hint" style={{ marginTop: 10 }}>
        These are <b>payment receipts</b>, not GST tax invoices — they carry no GST, invoice series or
        place of supply. Ask us if you need a tax invoice for input credit.
      </div>
    </div>
  );
}

function Pricing() {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.myPricing().then(setD).catch((e) => setMsg({ ok: false, text: e.message }));
  useEffect(() => { load(); }, []);
  if (!d) return <div className="muted">Loading…</div>;

  async function ask(p) {
    if (!confirm(`Ask to move to ${p.name} (${inr(p.price_monthly)}/month)? This doesn't charge you — we'll get in touch to arrange it.`)) return;
    setBusy(true); setMsg(null);
    try {
      const r = await api.requestUpgrade(p.id);
      setMsg({ ok: true, text: r.message });
      load();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }
  async function cancel() {
    setBusy(true);
    try { await api.cancelUpgrade(); setMsg({ ok: true, text: "Request withdrawn." }); load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }

  const requested = d.plans.find((p) => p.id === d.requested_plan_id);

  return (
    <div className="admin-form">
      <div className="settings-note">
        <b>💎 Plans.</b> Pick the one that fits and we'll arrange the change — there's no card on file
        and nothing is charged here. Your data and settings are untouched by a plan change.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}
      {requested && (
        <div className="alert alert-warn">
          <b>Change requested:</b> {requested.name}. We'll contact you to arrange it.{" "}
          <button className="btn btn-sm" style={{ marginLeft: 8 }} disabled={busy} onClick={cancel}>
            Withdraw
          </button>
        </div>
      )}

      <div className="price-grid">
        {d.plans.map((p) => {
          const current = p.id === d.current_plan_id;
          return (
            <div key={p.id} className={`price-card ${current ? "price-card-current" : ""}`}>
              {current && <div className="price-badge">Your plan</div>}
              <div className="price-name">{p.name}</div>
              <div className="price-amt">
                {p.price_monthly ? inr(p.price_monthly) : "Free"}
                {p.price_monthly ? <span className="price-per">/month</span> : null}
              </div>
              <ul className="price-feats">
                <li><b>{p.max_employees}</b> employees</li>
                <li><b>{p.daily_llm_quota}</b> AI questions / day</li>
                <li>Website widget, CRM API &amp; Live Chat</li>
                <li>Unlimited price &amp; inventory look-ups</li>
              </ul>
              {current ? (
                <button className="btn btn-sm" disabled>Current plan</button>
              ) : (
                <button className="btn btn-sm btn-primary" disabled={busy || p.id === d.requested_plan_id}
                  onClick={() => ask(p)}>
                  {p.id === d.requested_plan_id ? "Requested ✓" : "Request this plan"}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className="conn-hint">
        Price and inventory look-ups are never limited — they read your own database and cost nothing.
        The daily cap applies only to AI-written answers.
      </div>
    </div>
  );
}


export default function Billing() {
  const [tab, setTab] = useState("plan");
  const TABS = [
    ["plan", "Plan & Usage"],
    ["payments", "Payments"],
    ["pricing", "Pricing"],
  ];
  return (
    <div className="page">
      <div className="page-head">
        <h2>Billing</h2>
        <p className="muted">Your plan, what you've paid, and what else is available.</p>
      </div>
      <BillingBanner />
      <div className="admin-subtabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={`admin-subtab ${tab === id ? "admin-subtab-active" : ""}`}
            onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === "plan" && <PlanUsage />}
      {tab === "payments" && <Payments />}
      {tab === "pricing" && <Pricing />}
    </div>
  );
}
