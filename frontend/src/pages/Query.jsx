import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import BlockRenderer from "../components/BlockRenderer.jsx";
import Citations, { ConfidenceBadge } from "../components/Citations.jsx";
import Icon from "../components/Icons.jsx";

// One stable session id per browser session so follow-ups keep context (§10).
function useSessionId() {
  const ref = useRef(null);
  if (!ref.current) {
    ref.current =
      sessionStorage.getItem("qsession") ||
      (() => {
        const id = "web-" + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem("qsession", id);
        return id;
      })();
  }
  return ref.current;
}

const SUGGESTIONS = [
  "Golf Hills 3BHK price and payment plan",
  "Palm Greens possession",
  "Compare Golf Hills and Palm Greens",
  "Golf Hills inventory",
];

// Cap query length (matches the backend) so a huge paste can't inflate token cost.
const MAX_QUERY_LEN = 1000;

export default function Query() {
  const sessionId = useSessionId();
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState([]); // {query, response|error}
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const scrollRef = useRef(null);
  const recognitionRef = useRef(null);

  const speechSupported =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);

  function toggleVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = "en-IN"; // handles Indian-English + common Hinglish terms
    rec.interimResults = false;
    rec.onresult = (e) => setInput(e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [turns, loading]);

  async function ask(q) {
    const query = (q ?? input).trim();
    if (!query || loading) return;
    setInput("");
    setLoading(true);
    setTurns((t) => [...t, { query, pending: true }]);
    try {
      const response = await api.query(query, sessionId);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { query, response } : x)));
    } catch (err) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { query, error: err.message } : x)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="query-page">
      <div className="page-head">
        <h2>Ask the Knowledge Guru</h2>
        <p className="muted">Prices &amp; plans come from the database. Amenities from brochures. Always cited.</p>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="empty-state">
            <div className="empty-emoji">🏠</div>
            <p>Ask about any project — price, payment plan, possession, amenities, or compare two.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div className="turn" key={i}>
            <div className="user-bubble">{turn.query}</div>

            {turn.pending && <div className="answer loading-answer"><span className="dots"><i/><i/><i/></span> Thinking…</div>}

            {turn.error && <div className="answer alert alert-error">{turn.error}</div>}

            {turn.response && (
              <div className={`answer ${turn.response.not_available ? "answer-empty" : ""}`}>
                <div className="answer-meta">
                  {turn.response.handlers_used?.map((h) => (
                    <span key={h} className={`handler-chip handler-${h}`}>{h}</span>
                  ))}
                  {turn.response.resolved_from_memory && (
                    <span className="handler-chip handler-memory">from context</span>
                  )}
                  {turn.response.resolved_via === "fuzzy" && (
                    <span className="handler-chip handler-fuzzy">corrected spelling</span>
                  )}
                  {turn.response.limit_reached && (
                    <span className="handler-chip handler-limit">daily limit reached</span>
                  )}
                  {turn.response.cached && (
                    <span className="handler-chip handler-cached">⚡ cached</span>
                  )}
                  {turn.response.unverified && (
                    <span className="handler-chip handler-unverified">🌐 Internet · Not confident</span>
                  )}
                  {!turn.response.not_available && <ConfidenceBadge value={turn.response.confidence} />}
                </div>

                {turn.response.resolution_note && (
                  <div className="resolution-note">🔎 {turn.response.resolution_note}</div>
                )}

                {turn.response.unverified && (
                  <div className="unverified-note">
                    ⚠️ This is <b>not</b> from your company data — it's an AI answer from general
                    knowledge and may be inaccurate. <b>Verify before sharing, especially prices.</b>
                  </div>
                )}

                {turn.response.content?.blocks?.map((b, j) => <BlockRenderer key={j} block={b} />)}
                <Citations citations={turn.response.citations} />

                {turn.response.suggestions?.length > 0 && i === turns.length - 1 && (
                  <div className="followups">
                    {turn.response.suggestions.map((s) => (
                      <button key={s} className="chip chip-sm" onClick={() => ask(s)}>{s}</button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {input.length > MAX_QUERY_LEN * 0.8 && (
        <div className="char-count muted">{input.length}/{MAX_QUERY_LEN}</div>
      )}
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <input
          className="composer-input"
          placeholder={listening ? "Listening…" : "Ask about price, payment plan, possession, amenities…"}
          value={input}
          maxLength={MAX_QUERY_LEN}
          onChange={(e) => setInput(e.target.value)}
        />
        {speechSupported && (
          <button
            type="button"
            className={`btn mic-btn ${listening ? "mic-on" : ""}`}
            onClick={toggleVoice}
            title="Voice input"
          >
            <Icon name="mic" size={17} />
          </button>
        )}
        <button className="btn btn-primary" disabled={loading || !input.trim()}>Ask</button>
      </form>
    </div>
  );
}
