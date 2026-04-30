import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { login, getMe } from "./api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(email, password);
      localStorage.setItem("token", data.access_token);
      const me = await getMe();
      localStorage.setItem("userEmail", me.email || email);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <h1>Sign in to AI Copilot</h1>
        <form onSubmit={handleSubmit}>
          <label>
            <span>Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            <span>Password</span>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p className="error-line" role="alert">
              {error}
            </p>
          )}
          <button disabled={loading} type="submit">
            {loading ? (
              <LogIn className="spin" size={18} />
            ) : (
              <LogIn size={18} />
            )}
            <span>{loading ? "Signing in..." : "Sign in"}</span>
          </button>
        </form>
        <p className="auth-switch">
          Need an account? <Link to="/register">Register</Link>
        </p>
      </section>
    </main>
  );
}
