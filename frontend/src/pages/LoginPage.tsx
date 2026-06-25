import { LoginForm } from "@/components/auth/LoginForm";

export function LoginPage(): JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <LoginForm />
    </div>
  );
}
