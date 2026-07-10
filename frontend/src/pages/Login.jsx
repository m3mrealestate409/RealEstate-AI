import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { Wordmark } from "../components/Logo.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@chaahat.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <Wordmark height={54} />
          <p className="muted" style={{ marginTop: 10, letterSpacing: "0.02em" }}>Knowledge Guru</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <label className="field">
          <span>Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoFocus />
        </label>
        <label className="field">
          <span>Password</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
        </label>

        <button className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <p className="muted small center">Demo: admin@chaahat.local / admin123</p>
      </form>
    </div>
  );
}
