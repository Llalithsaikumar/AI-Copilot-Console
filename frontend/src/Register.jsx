import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { register } from "./api";

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await register(email, password);
      const data = await login(email, password);
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("userEmail", email);
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
        <h1>Create your account</h1>
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
              <UserPlus className="spin" size={18} />
            ) : (
              <UserPlus size={18} />
            )}
            <span>{loading ? "Creating..." : "Create account"}</span>
          </button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}

async function login(email, password) {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || ""}/auth/login`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    }
  );
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.message || "Login failed");
  }
  return response.json();
}
