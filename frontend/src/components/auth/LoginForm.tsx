import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

export function LoginForm(): JSX.Element {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/chat");
    } catch {
      setError("Invalid credentials.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="w-80 space-y-3 rounded-lg bg-white p-6 shadow">
      <h1 className="text-xl font-semibold text-slate-800">Aegis RAG</h1>
      <input
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
        autoComplete="username"
        className="w-full rounded border border-slate-300 px-3 py-2"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        autoComplete="current-password"
        className="w-full rounded border border-slate-300 px-3 py-2"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded bg-slate-800 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
