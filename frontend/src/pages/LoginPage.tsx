import { LoginForm } from "@/components/auth/LoginForm";

export function LoginPage(): JSX.Element {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 p-4">
      {/* Aurora backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-sidebar" />
      <div className="pointer-events-none absolute -left-40 top-1/3 h-96 w-96 rounded-full bg-indigo-600/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-emerald-500/20 blur-3xl" />
      <div className="relative z-10">
        <LoginForm />
      </div>
    </div>
  );
}
