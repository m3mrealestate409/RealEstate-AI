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
  const [name, setName] = useState("");
  const [avatar, setAvatar] = useState(null);        // served path
  const [hint, setHint] = useState("");
  const [nameHint, setNameHint] = useState("Riya");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";
  const avatarSrc = avatar ? (avatar.startsWith("http") ? avatar : API_BASE_URL + avatar) : null;
  const initial = (name || nameHint || "A").trim().charAt(0).toUpperCase();

  useEffect(() => {
    api.getAssistantConfig().then((c) => {
      setPersona(c.persona || ""); setName(c.name || ""); setAvatar(c.avatar_url || null);
      setHint(c.hint || ""); setNameHint(c.name_hint || "Riya");
    }).catch(() => {});
  }, []);

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const r = await api.setAssistantConfig({ persona, name });
      setPersona(r.persona || ""); setName(r.name || "");
      setMsg({ ok: true, text: "Saved — applies everywhere (website, CRM, WhatsApp, app)." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  async function onAvatar(file) {
    if (!file) return;
    setUploading(true); setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.uploadAssistantAvatar(fd);
      setAvatar(r.avatar_url || null);
      setMsg({ ok: true, text: "Profile picture updated." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setUploading(false); }
  }
  async function removeAvatar() {
    setUploading(true); setMsg(null);
    try { await api.deleteAssistantAvatar(); setAvatar(null); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setUploading(false); }
  }

  return (
    <div className="int-greeting int-persona">
      <b>🎭 Assistant identity &amp; persona — applies to every channel</b>
      <p className="muted">
        Give your assistant a name, photo and personality — shown on the website chat widget and used
        across CRM, WhatsApp and the app. It only changes look/tone; prices &amp; facts stay grounded.
      </p>

      <div className="persona-id-row">
        <div className="persona-avatar" style={avatarSrc ? { backgroundImage: `url(${avatarSrc})` } : null}>
          {!avatarSrc && <span>{initial}</span>}
        </div>
        <div className="persona-id-fields">
          <label className="field"><span>Assistant name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={nameHint} maxLength={40} />
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <label className="btn btn-sm" style={{ cursor: "pointer" }}>
              {uploading ? "Uploading…" : "Upload photo"}
              <input type="file" accept="image/*" hidden onChange={(e) => onAvatar(e.target.files[0])} />
            </label>
            {avatar && <button type="button" className="btn btn-sm btn-ghost" onClick={removeAvatar} disabled={uploading}>Remove</button>}
          </div>
        </div>
      </div>

      <label className="field" style={{ marginTop: 4 }}><span>Personality / master prompt</span>
        <textarea rows={4} value={persona} onChange={(e) => setPersona(e.target.value)} placeholder={hint} />
      </label>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        {!persona && hint && <button type="button" className="btn btn-sm" onClick={() => setPersona(hint)}>Use example</button>}
        {msg && <span style={{ fontSize: 13, color: msg.ok ? "var(--muted)" : "#c0392b" }}>{msg.text}</span>}
      </div>
    </div>
  );
}

function linesToHeaders(text) {
  const out = {};
  (text || "").split("\n").forEach((ln) => {
    const i = ln.indexOf(":");
    if (i > 0) { const k = ln.slice(0, i).trim(); const v = ln.slice(i + 1).trim(); if (k) out[k] = v; }
  });
  return out;
}
function headersToLines(obj) {
  return Object.entries(obj || {}).map(([k, v]) => `${k}: ${v}`).join("\n");
}

const DEFAULT_BODY_TEMPLATE = '{"text": "{{text}}"}';

function NotificationSettings() {
  const [provider, setProvider] = useState("off");
  const [cfg, setCfg] = useState({});
  const [headersText, setHeadersText] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    api.getNotifyConfig().then((r) => {
      setProvider(r.provider || "off");
      setCfg(r.config || {});
      setHeadersText(headersToLines(r.config?.headers));
    }).catch(() => {});
  }, []);

  const set = (k, v) => setCfg((s) => ({ ...s, [k]: v }));

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const config = { ...cfg };
      if (provider === "webhook") config.headers = linesToHeaders(headersText);
      const r = await api.setNotifyConfig(provider, config);
      setProvider(r.provider); setCfg(r.config || {});
      setMsg({ ok: true, text: "Saved." });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }
  async function test() {
    setTesting(true); setMsg(null);
    try { const r = await api.testNotifyConfig(); setMsg({ ok: true, text: "Test sent ✓ " + (r.detail || "") }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setTesting(false); }
  }

  return (
    <div className="int-greeting int-persona">
      <b>🔔 New-chat notifications</b>
      <p className="muted">
        Get pinged the moment a new visitor starts chatting, so someone can jump in from Live Chat.
        Works with <b>Telegram</b> (free, official) or any <b>webhook</b> — an unofficial WhatsApp service,
        WhatsApp Cloud API, Zapier/Make, Slack, etc.
      </p>

      <label className="field" style={{ maxWidth: 280 }}><span>Notify via</span>
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
            Create a bot with <b>@BotFather</b>, add it to your team group, then get the group's chat id
            (e.g. via <b>@getidsbot</b>). Notifications land in that group.
          </p>
        </div>
      )}

      {provider === "webhook" && (
        <>
          <label className="field"><span>Webhook URL</span>
            <input value={cfg.url || ""} onChange={(e) => set("url", e.target.value)} placeholder="https://your-service.com/send" />
          </label>
          <label className="field"><span>Body template (JSON, use <code>{"{{text}}"}</code>)</span>
            <textarea rows={3} value={cfg.body_template || ""} onChange={(e) => set("body_template", e.target.value)} placeholder={DEFAULT_BODY_TEMPLATE} />
          </label>
          <label className="field"><span>Headers (optional, one <code>Key: Value</code> per line)</span>
            <textarea rows={2} value={headersText} onChange={(e) => setHeadersText(e.target.value)} placeholder={"Authorization: Bearer xxxxx"} />
          </label>
          <p className="muted small" style={{ margin: 0 }}>
            Match your service's shape. Unofficial WhatsApp: <code>{'{"number":"9198…","message":"{{text}}"}'}</code>.
            WhatsApp Cloud API: point the URL at graph.facebook.com and add the <code>Authorization</code> header.
          </p>
        </>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginTop: 10 }}>
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        {provider !== "off" && <button type="button" className="btn btn-sm" onClick={test} disabled={testing}>{testing ? "Sending…" : "Send test"}</button>}
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
      <NotificationSettings />
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
