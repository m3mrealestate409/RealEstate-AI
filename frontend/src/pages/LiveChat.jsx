import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

// Distinct gradient per visitor (picked by hashing the session id) so the
// inbox feels like a list of people, not raw session strings.
const AVA_GRADS = [
  "linear-gradient(135deg,#6366f1,#8b5cf6)",
  "linear-gradient(135deg,#0ea5e9,#6366f1)",
  "linear-gradient(135deg,#f59e0b,#f43f5e)",
  "linear-gradient(135deg,#10b981,#0ea5e9)",
  "linear-gradient(135deg,#ec4899,#8b5cf6)",
  "linear-gradient(135deg,#14b8a6,#22c55e)",
];
function hashCode(s) {
  let h = 0;
  for (let i = 0; i < (s || "").length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}
const gradFor = (sid) => AVA_GRADS[hashCode(sid) % AVA_GRADS.length];
// "web-3tbi5fdk" → "Visitor 5FDK" (friendly, human-scannable)
function visitorLabel(sid) {
  const tail = (sid || "").replace(/^web-/, "").slice(-4).toUpperCase();
  return `Visitor ${tail || "?"}`;
}
function relTime(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
const msgTime = (iso) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

const PersonIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
);
const SendIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

export default function LiveChat() {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);      // session_id
  const [convo, setConvo] = useState(null);        // {mode, agent, online, messages}
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);
  const activeRef = useRef(null);
  activeRef.current = active;

  // Poll the inbox every 4s.
  useEffect(() => {
    let alive = true;
    const load = () => api.liveSessions().then((s) => { if (alive) setSessions(s); }).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // Poll the open conversation every 2.5s.
  useEffect(() => {
    if (!active) { setConvo(null); return; }
    let alive = true;
    const load = () => api.liveTranscript(active).then((c) => { if (alive && activeRef.current === active) setConvo(c); }).catch(() => {});
    load();
    const t = setInterval(load, 2500);
    return () => { alive = false; clearInterval(t); };
  }, [active]);

  useEffect(() => { scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight); }, [convo]);

  async function takeover() { setBusy(true); try { await api.liveTakeover(active); await refresh(); } finally { setBusy(false); } }
  async function release() { setBusy(true); try { await api.liveRelease(active); await refresh(); } finally { setBusy(false); } }
  async function refresh() { try { setConvo(await api.liveTranscript(active)); } catch { /* ignore */ } }
  async function send(e) {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true); setText("");
    try { await api.liveSend(active, t); await refresh(); }
    catch (err) { setText(t); }
    finally { setBusy(false); }
  }

  const isHuman = convo?.mode === "human";
  return (
    <div className="page live-page">
      <div className="page-head">
        <h2>💬 Live Chat</h2>
        <p className="muted">Watch website conversations in real time and take over from the AI when needed.</p>
      </div>

      <div className="live-wrap">
        {/* ---- Inbox ---- */}
        <div className="live-list">
          <div className="live-list-head">
            <span>Conversations</span>
            <span className="live-count">{sessions.length}</span>
          </div>
          {sessions.length === 0 && (
            <div className="live-empty-inbox">No active chats right now.<br />New visitors will appear here.</div>
          )}
          {sessions.map((s) => (
            <button key={s.session_id} className={`live-item ${active === s.session_id ? "live-item-active" : ""}`}
              onClick={() => setActive(s.session_id)}>
              <div className="live-ava" style={{ background: gradFor(s.session_id) }}>
                <PersonIcon />
                <span className={`live-presence ${s.online ? "" : "off"}`} title={s.online ? "Online" : "Offline"}></span>
              </div>
              <div className="live-item-body">
                <div className="live-item-top">
                  <span className="live-name">{visitorLabel(s.session_id)}</span>
                  <span className="live-item-time">{relTime(s.last_activity)}</span>
                </div>
                <div className="live-item-bottom">
                  <span className="live-item-last">{s.last_message || "—"}</span>
                  <span className={`live-mode ${s.mode === "human" ? "live-mode-human" : ""}`}>
                    {s.mode === "human" ? (s.agent || "Human") : "AI"}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* ---- Conversation ---- */}
        <div className="live-convo">
          {!active && (
            <div className="live-empty">
              <div className="live-empty-ico">💬</div>
              <b>Select a conversation</b>
              <span className="small">Pick a visitor on the left to watch their chat live.</span>
            </div>
          )}
          {active && convo && (
            <>
              <div className="live-convo-head">
                <div className="live-head-left">
                  <div className="live-ava live-ava-sm" style={{ background: gradFor(active) }}>
                    <PersonIcon />
                    <span className={`live-presence ${convo.online ? "" : "off"}`}></span>
                  </div>
                  <div>
                    <div className="live-head-name">{visitorLabel(active)}</div>
                    <div className={`live-status ${convo.online ? "on" : "off"}`}>
                      <i></i>{convo.online ? "Online now" : "Left the site"}
                    </div>
                  </div>
                </div>
                <span className={`live-mode ${isHuman ? "live-mode-human" : ""}`}>
                  {isHuman ? `👤 ${convo.agent || "You"}` : "✦ AI handling"}
                </span>
              </div>

              <div className="live-msgs" ref={scrollRef}>
                {convo.messages.map((m) =>
                  m.role === "system" ? (
                    <div key={m.id} className="live-sysrow"><span className="live-sys">{m.text}</span></div>
                  ) : (
                    <div key={m.id} className={`live-row ${m.role === "user" ? "live-row-visitor" : "live-row-team"}`}>
                      <div className={`live-mava live-mava-${m.role}`}>
                        {m.role === "user" ? <PersonIcon /> : m.role === "ai" ? "✦" : (convo.agent || "A").trim().charAt(0).toUpperCase()}
                      </div>
                      <div className="live-mcol">
                        <div className={`live-bubble live-bubble-${m.role}`}>{m.text}</div>
                        <div className="live-msg-time">
                          {m.role === "user" ? "Visitor" : m.role === "ai" ? "AI Assistant" : (convo.agent || "You")} · {msgTime(m.at)}
                        </div>
                      </div>
                    </div>
                  )
                )}
              </div>

              <div className="live-actions">
                {!isHuman ? (
                  <button className="live-takeover" onClick={takeover} disabled={busy || !convo.online}
                    title={convo.online ? "" : "Visitor has left — can't take over"}>
                    {convo.online ? <>🎧 Take over this chat</> : <>Visitor offline — can't take over</>}
                  </button>
                ) : (
                  <form className="live-composer" onSubmit={send}>
                    <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your reply to the visitor…" />
                    <button className="live-send" disabled={busy || !text.trim()} title="Send"><SendIcon /></button>
                    <button type="button" className="live-return" onClick={release} disabled={busy}>↩ Return to AI</button>
                  </form>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
