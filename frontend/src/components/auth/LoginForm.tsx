import { Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
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
      setError("Invalid credentials. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="w-full max-w-sm animate-slide-up rounded-2xl border border-slate-200/70 bg-white/90 p-7 shadow-glow backdrop-blur">
      <div className="mb-6 flex flex-col items-center text-center">
        <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-indigo-600 shadow-lg shadow-indigo-600/30">
          <ShieldCheck className="h-6 w-6 text-white" />
        </div>
        <h1 className="text-xl font-semibold text-slate-900">Welcome to Aegis RAG</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to your sovereign workspace</p>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="you@org"
            autoComplete="username"
          />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </div>
        {error && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
            {error}
          </div>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="mt-5 text-center text-xs text-slate-400">
        🔒 Processed entirely on-premise · zero egress
      </p>
    </div>
  );
}
