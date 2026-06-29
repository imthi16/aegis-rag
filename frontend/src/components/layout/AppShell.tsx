import {
  FileText,
  FlaskConical,
  LogOut,
  MessagesSquare,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import { initials } from "@/lib/ui";

interface NavItem {
  to: string;
  label: string;
  icon: typeof FileText;
  show: boolean;
}

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const { user, roles, signOut } = useAuth();
  const isAdmin = roles.includes("admin");
  const isAuditor = roles.includes("compliance_auditor") || isAdmin;

  const items: NavItem[] = [
    { to: "/chat", label: "Chat", icon: MessagesSquare, show: true },
    { to: "/documents", label: "Documents", icon: FileText, show: true },
    { to: "/audit", label: "Audit", icon: ScrollText, show: isAuditor },
    { to: "/eval", label: "Evaluation", icon: FlaskConical, show: isAdmin },
  ];

  return (
    <div className="flex min-h-screen bg-app">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-sidebar text-slate-300 md:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-500/20 ring-1 ring-indigo-400/30">
            <ShieldCheck className="h-5 w-5 text-indigo-300" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">Aegis RAG</div>
            <div className="text-[11px] text-slate-400">Sovereign · air-gapped</div>
          </div>
        </div>

        <nav className="mt-2 flex-1 space-y-1 px-3">
          {items
            .filter((i) => i.show)
            .map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-white/10 text-white shadow-inner"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
                  )
                }
              >
                <Icon className="h-[18px] w-[18px]" />
                {label}
              </NavLink>
            ))}
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-indigo-500/30 text-xs font-semibold text-indigo-100">
              {initials(user?.username ?? "?")}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-medium text-white">{user?.username}</div>
              <div className="truncate text-[11px] text-slate-400">{roles.join(", ") || "—"}</div>
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              title="Sign out"
              className="grid h-8 w-8 place-items-center rounded-md text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-h-screen flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white/70 px-4 py-3 backdrop-blur md:hidden">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-600" />
            <span className="font-semibold text-slate-800">Aegis RAG</span>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="text-sm text-slate-500"
          >
            Sign out
          </button>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
