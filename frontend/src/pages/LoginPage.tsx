import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { errorText } from "../api";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // set when the app auto-logged out due to an expired/invalid token
  const [expired, setExpired] = useState(() => {
    if (localStorage.getItem("scraper_expired")) {
      localStorage.removeItem("scraper_expired");
      return true;
    }
    return false;
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setExpired(false);
    try {
      await login(username, password, remember);
      navigate("/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <h1>🕷️ Scraper CMS</h1>
        <p className="muted">Sign in to continue</p>
        {expired && <div className="alert">Your session expired. Please sign in again.</div>}
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <label className="check">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Stay signed in for 30 days
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}
