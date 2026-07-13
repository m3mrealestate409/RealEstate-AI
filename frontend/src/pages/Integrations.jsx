import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Where the engine's API lives (same value the app itself uses).
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

// Add a new integration here and it appears in the list — nothing else to wire.
const INTEGRATIONS = [
  { id: "wordpress", icon: "🟦", name: "WordPress", blurb: "Add a chat widget to any WordPress site.", status: "available" },
  { id: "website", icon: "🔗", name: "Website / CRM (API)", blurb: "Call the engine from your own site, CRM, or app.", status: "available" },
  { id: "whatsapp", icon: "💬", name: "WhatsApp", blurb: "A WhatsApp bot that answers from your data.", status: "soon" },
  { id: "voice", icon: "📞", name: "Voice / Calling agent", blurb: "Answer questions over a phone call.", status: "soon" },
];

function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="code-block">
      <pre><code>{code}</code></pre>
      <button type="button" className="btn btn-sm" onClick={() => {
        navigator.clipboard?.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500);
      }}>{copied ? "Copied ✓" : "Copy"}</button>
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="int-step">
      <div className="int-step-n">{n}</div>
      <div className="int-step-body"><b>{title}</b>{children}</div>
    </div>
  );
}

function AssistantPersona() {
  const [persona, setPersona] = useState("");
  const [hint, setHint] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    api.getAssistantConfig().then((c) => { setPersona(c.persona || ""); setHint(c.hint || ""); }).catch(() => {});
  }, []);
  async function save() {
    setSaving(true); setMsg(null);
    try {
      const r = await api.setAssistantConfig(persona);
      setPersona(r.persona || "");
      setMsg({ ok: true, text: "Saved — applies everywhere (website, CRM, WhatsApp, app)." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  return (
    <div className="int-greeting int-persona">
      <b>🎭 Assistant persona — applies to every channel</b>
      <p className="muted">
        Give your assistant an identity, voice and style — used on the website widget, CRM, WhatsApp and the app.
        It only changes tone/personality; prices &amp; facts always stay grounded (never invented).
      </p>
      <textarea rows={4} value={persona} onChange={(e) => setPersona(e.target.value)} placeholder={hint} />
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save persona"}</button>
        {!persona && hint && <button type="button" className="btn btn-sm" onClick={() => setPersona(hint)}>Use example</button>}
        {msg && <span style={{ fontSize: 13, color: msg.ok ? "var(--muted)" : "#c0392b" }}>{msg.text}</span>}
      </div>
    </div>
  );
}

function WidgetGreeting() {
  const [greeting, setGreeting] = useState("");
  const [def, setDef] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    api.getWidgetConfig().then((c) => { setGreeting(c.greeting || ""); setDef(c.default || ""); }).catch(() => {});
  }, []);
  async function save() {
    setSaving(true); setMsg(null);
    try {
      const r = await api.setWidgetConfig(greeting);
      setGreeting(r.greeting || "");
      setMsg({ ok: true, text: "Saved — your site updates live (just refresh)." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  return (
    <div className="int-greeting">
      <b>💬 Chat greeting message</b>
      <p className="muted">Shown as a teaser next to the chat bubble and as the first message. Edit anytime — the widget picks it up live (no code change).</p>
      <textarea rows={2} value={greeting} onChange={(e) => setGreeting(e.target.value)} placeholder={def} />
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save greeting"}</button>
        {msg && <span style={{ fontSize: 13, color: msg.ok ? "var(--muted)" : "#c0392b" }}>{msg.text}</span>}
      </div>
    </div>
  );
}

function WordPressGuide() {
  const snippet =
    `<script src="${API_BASE}/static/widget.js"\n` +
    `        data-api-url="${API_BASE}"\n` +
    `        data-api-key="YOUR_API_KEY"\n` +
    `        data-title="Ask about our projects"\n` +
    `        data-accent="#6b46ff"></script>`;
  return (
    <div className="int-guide">
      <Step n="1" title="Create an API key">
        <p className="muted">Go to the <b>🔌 API Keys</b> tab → <b>Create key</b> → copy it (shown once).</p>
      </Step>
      <Step n="2" title="Install a snippet plugin in WordPress">
        <p className="muted">In WordPress admin → Plugins → add <b>“WPCode”</b> or <b>“Insert Headers and Footers”</b> (free).</p>
      </Step>
      <Step n="3" title="Paste this script (Footer / site-wide)">
        <p className="muted">Replace <code>YOUR_API_KEY</code> with the key from step 1.</p>
        <CodeBlock code={snippet} />
      </Step>
      <Step n="4" title="Save → open any page">
        <p className="muted">A chat bubble appears at the bottom-right. Click it and ask a question. Done ✅</p>
      </Step>
      <div className="int-note">
        Customise with <code>data-title</code> (header text) and <code>data-accent</code> (brand colour).
        For production, put the key behind a small server-side proxy so it isn’t visible in the page.
      </div>
      <WidgetGreeting />
    </div>
  );
}

function WebsiteGuide() {
  const curl =
    `curl -X POST ${API_BASE}/v1/query \\\n` +
    `  -H "X-API-Key: YOUR_API_KEY" \\\n` +
    `  -H "Content-Type: application/json" \\\n` +
    `  -d '{"query":"Golf Hills 3BHK price","format":"text"}'`;
  const js =
    `const res = await fetch("${API_BASE}/v1/query", {\n` +
    `  method: "POST",\n` +
    `  headers: { "X-API-Key": process.env.RAG_API_KEY, "Content-Type": "application/json" },\n` +
    `  body: JSON.stringify({ query, session_id: "crm-" + userId, format: "text" }),\n` +
    `});\n` +
    `const { answer_text } = await res.json();`;
  return (
    <div className="int-guide">
      <Step n="1" title="Create an API key">
        <p className="muted">🔌 API Keys → Create key. Send it as an <code>X-API-Key</code> header on every request.</p>
      </Step>
      <Step n="2" title="Ask the engine a question">
        <p className="muted">Call <code>POST /v1/query</code>. Use <code>format</code>: <code>text</code> (chat/CRM), <code>voice</code> (spoken), or <code>blocks</code> (rich UI). The reply’s <code>answer_text</code> is ready to display.</p>
        <CodeBlock code={curl} />
      </Step>
      <Step n="3" title="From your CRM / app (server-side)">
        <CodeBlock code={js} />
      </Step>
      <div className="int-note">
        Full reference: <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">{API_BASE}/docs</a> (OpenAPI).
        A key only ever sees <b>your organisation’s</b> data.
      </div>
    </div>
  );
}

function SoonGuide({ name }) {
  return (
    <div className="int-guide">
      <div className="int-note">
        <b>{name} — coming soon.</b> The engine is ready (API + voice/text answer formats); this channel
        needs a provider + a small adapter, which we’ll add when you choose a provider.
      </div>
    </div>
  );
}

export default function Integrations() {
  const [active, setActive] = useState("wordpress");
  const cur = INTEGRATIONS.find((i) => i.id === active);
  return (
    <div className="admin-form">
      <div className="settings-note">
        Connect the engine to your other tools. Pick a channel below to see step-by-step instructions.
        All integrations use an <b>API key</b> (🔌 API Keys tab) and stay scoped to your organisation.
      </div>
      <AssistantPersona />
      <div className="int-cards">
        {INTEGRATIONS.map((i) => (
          <button key={i.id} type="button"
            className={`int-card ${active === i.id ? "int-card-active" : ""}`}
            onClick={() => setActive(i.id)}>
            <span className="int-ico">{i.icon}</span>
            <span className="int-name">{i.name}{i.status === "soon" && <span className="int-soon">Soon</span>}</span>
            <span className="int-blurb">{i.blurb}</span>
          </button>
        ))}
      </div>

      <div className="int-guide-wrap">
        <h3>{cur.icon} {cur.name}</h3>
        {active === "wordpress" && <WordPressGuide />}
        {active === "website" && <WebsiteGuide />}
        {(active === "whatsapp" || active === "voice") && <SoonGuide name={cur.name} />}
      </div>
    </div>
  );
}
