import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

export default function LiveChat() {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);      // session_id
  const [convo, setConvo] = useState(null);        // {mode, agent, messages}
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
    <div className="page">
      <div className="page-head">
        <h2>💬 Live Chat</h2>
        <p className="muted">Watch website conversations in real time and take over from the AI when needed.</p>
      </div>
      <div className="live-wrap">
        <div className="live-list">
          {sessions.length === 0 && <div className="muted" style={{ padding: 12 }}>No active chats right now.</div>}
          {sessions.map((s) => (
            <button key={s.session_id} className={`live-item ${active === s.session_id ? "live-item-active" : ""}`}
              onClick={() => setActive(s.session_id)}>
              <div className="live-item-top">
                <span className="live-id">
                  <span className={`live-dot ${s.online ? "" : "live-dot-off"}`} title={s.online ? "Online" : "Offline"}></span>
                  {s.session_id}
                </span>
                <span className={`live-mode ${s.mode === "human" ? "live-mode-human" : ""}`}>{s.mode === "human" ? (s.agent ? s.agent : "Human") : "AI"}</span>
              </div>
              <div className="live-item-last">{s.last_message || "—"}</div>
              <div className="live-item-time">{s.last_activity ? new Date(s.last_activity).toLocaleTimeString() : ""}</div>
            </button>
          ))}
        </div>

        <div className="live-convo">
          {!active && <div className="muted live-empty">Select a conversation to view it.</div>}
          {active && convo && (
            <>
              <div className="live-convo-head">
                <span>
                  <span className={`live-dot ${convo.online ? "" : "live-dot-off"}`}></span>
                  {active} · <span className="muted small">{convo.online ? "online" : "offline"}</span>
                </span>
                <span className={`live-mode ${isHuman ? "live-mode-human" : ""}`}>{isHuman ? `Human · ${convo.agent || "you"}` : "AI"}</span>
              </div>
              <div className="live-msgs" ref={scrollRef}>
                {convo.messages.map((m) => (
                  <div key={m.id} className={`live-msg live-${m.role}`}>
                    {m.role === "system"
                      ? <span className="live-sys">{m.text}</span>
                      : <><span className="live-role">{m.role === "user" ? "Visitor" : m.role === "ai" ? "AI" : "You"}</span><span className="live-text">{m.text}</span></>}
                  </div>
                ))}
              </div>
              <div className="live-actions">
                {!isHuman
                  ? <button className="btn btn-primary" onClick={takeover} disabled={busy || !convo.online}
                      title={convo.online ? "" : "Visitor has left — can't take over"}>
                      {convo.online ? "Take over this chat" : "Visitor offline — can't take over"}
                    </button>
                  : (
                    <form className="live-composer" onSubmit={send}>
                      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your reply to the visitor…" />
                      <button className="btn btn-primary" disabled={busy || !text.trim()}>Send</button>
                      <button type="button" className="btn btn-ghost" onClick={release} disabled={busy}>Return to AI</button>
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
