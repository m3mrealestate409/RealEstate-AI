import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Admin-only. Lets the admin pick the LLM provider and paste a key.
// The key is sent to the backend over HTTPS and stored SERVER-SIDE only —
// it is never kept in the browser and only ever shown masked (§19).
export default function AiSettings() {
  const [data, setData] = useState(null);
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [embedding, setEmbedding] = useState("mock");
  const [msg, setMsg] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  async function load() {
    const res = await api.getLlmSettings();
    setData(res);
    setProvider(res.current.provider);
    setModel(res.current.model);
    setEmbedding(res.current.embedding_provider);
  }
  useEffect(() => { load(); }, []);

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    setTestResult(null);
    try {
      const body = { provider, model, embedding_provider: embedding };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      await api.updateLlmSettings(body);
      setApiKey("");
      await load();
      setMsg({ ok: true, text: "Saved. New provider is now active." });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.testLlm());
    } catch (err) {
      setTestResult({ ok: false, error: err.message });
    } finally {
      setTesting(false);
    }
  }

  if (!data) return <div className="muted">Loading…</div>;
  const cur = data.current;

  return (
    <div className="admin-form">
      {msg && <div className={`alert ${msg.ok ? "alert-ok" : "alert-error"}`}>{msg.text}</div>}

      <div className="settings-status">
        <div>
          <div className="muted small">Active provider</div>
          <div className="status-line">
            <span className={`handler-chip handler-${cur.provider === "mock" ? "" : "llm"}`}>{cur.provider}</span>
            <span className="muted">{cur.model}</span>
            {cur.key_set ? (
              <span className="status-chip chip-green">Key set · {cur.key_masked}</span>
            ) : (
              <span className="status-chip chip-amber">No key (mock mode)</span>
            )}
          </div>
        </div>
        <button type="button" className="btn" onClick={test} disabled={testing}>
          {testing ? "Testing…" : "Test connection"}
        </button>
      </div>

      {testResult && (
        <div className={`alert ${testResult.ok ? "alert-ok" : "alert-error"}`}>
          {testResult.ok
            ? `✓ ${testResult.provider} (${testResult.model}) responded: ${testResult.sample}`
            : `✗ ${testResult.error}`}
        </div>
      )}

      <form onSubmit={save}>
        <div className="calc-fields">
          <label className="field">
            <span>Provider</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {data.supported_providers.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Model</span>
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gemini-1.5-flash" />
          </label>
          <label className="field">
            <span>Embeddings (for RAG)</span>
            <select value={embedding} onChange={(e) => setEmbedding(e.target.value)}>
              <option value="mock">mock (local, no key)</option>
              <option value="gemini">gemini</option>
            </select>
          </label>
          <label className="field">
            <span>API Key {cur.key_set && <em className="muted">(leave blank to keep current)</em>}</span>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={cur.key_set ? "•••••••• (unchanged)" : "Paste your API key"} />
          </label>
        </div>

        <div className="settings-note">
          🔒 The key is stored on the server only — never saved in your browser and shown only masked.
          Get a free Gemini key at <span className="mono">aistudio.google.com/apikey</span>.
        </div>

        <button className="btn btn-primary">Save settings</button>
      </form>
    </div>
  );
}
