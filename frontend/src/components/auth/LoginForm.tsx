import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { SovereignSeal3D } from "@/components/layout/SovereignSeal3D";
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
      setError("Credentials rejected. Verify and retry.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="hw hw-raise animate-slide-up rounded-xl backdrop-blur">
      <div className="flex flex-col items-center px-8 pb-2 pt-9 text-center">
        <SovereignSeal3D className="h-24 w-24" />
        <div className="mt-5 font-mono text-lg font-semibold tracking-[0.3em] text-fg">AEGIS</div>
        <div className="mt-1.5 eyebrow">Sovereign RAG Terminal</div>
      </div>

      <form onSubmit={submit} className="space-y-4 px-8 pb-6 pt-6">
        <div>
          <Label htmlFor="username">Operator</Label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username"
            autoComplete="username"
          />
        </div>
        <div>
          <Label htmlFor="password">Passphrase</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••"
            autoComplete="current-password"
          />
        </div>
        {error && (
          <div className="rounded-md bg-crimson/10 px-3 py-2 text-sm text-crimson ring-1 ring-inset ring-crimson/25">
            {error}
          </div>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {busy ? "Authenticating…" : "Enter terminal"}
        </Button>
      </form>

      <div className="flex items-center justify-center gap-2 border-t border-edge/12 px-8 py-3.5">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-jade/70" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-jade" />
        </span>
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
          Processed on-premise · zero egress
        </span>
      </div>
    </div>
  );
}
