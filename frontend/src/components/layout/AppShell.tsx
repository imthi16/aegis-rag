import {
  FileText,
  FlaskConical,
  LogOut,
  MessagesSquare,
  ScrollText,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import { initials } from "@/lib/ui";
import { SovereignMark } from "@/components/layout/SovereignMark";

interface NavItem {
  to: string;
  label: string;
  code: string;
  icon: typeof FileText;
  show: boolean;
}

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const { user, roles, signOut } = useAuth();
  const isAdmin = roles.includes("admin");
  const isAuditor = roles.includes("compliance_auditor") || isAdmin;

  const items: NavItem[] = [
    { to: "/chat", label: "Interrogate", code: "01", icon: MessagesSquare, show: true },
    { to: "/documents", label: "Corpus", code: "02", icon: FileText, show: true },
    { to: "/audit", label: "Ledger", code: "03", icon: ScrollText, show: isAuditor },
    { to: "/eval", label: "Evaluation", code: "04", icon: FlaskConical, show: isAdmin },
  ];

  return (
    <div className="flex min-h-screen bg-ink">
      {/* Command rail — a raised faceplate; its right edge casts onto the workspace. */}
      <aside className="sticky top-0 z-20 hidden h-screen w-64 shrink-0 flex-col border-r border-edge/12 bg-seam shadow-[10px_0_30px_-18px_rgba(0,0,0,0.95)] md:flex">
        <div className="flex items-center gap-3 px-5 pb-5 pt-6">
          <SovereignMark className="h-9 w-9 text-beacon" />
          <div className="leading-none">
            <div className="font-mono text-sm font-semibold tracking-[0.28em] text-fg">AEGIS</div>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
              Sovereign RAG
            </div>
          </div>
        </div>

        <div className="mx-5 mb-2 h-px bg-edge/12" />

        <nav className="mt-2 flex-1 space-y-0.5 px-3">
          {items
            .filter((i) => i.show)
            .map(({ to, label, code, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center gap-3 rounded-md py-2.5 pl-4 pr-3 text-sm transition-all",
                    isActive
                      ? "bg-raise text-fg shadow-e1"
                      : "text-fg-dim hover:bg-raise/60 hover:text-fg",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full transition-all",
                        isActive
                          ? "bg-beacon shadow-beacon"
                          : "bg-transparent group-hover:bg-edge/30",
                      )}
                    />
                    <Icon className={cn("h-[18px] w-[18px]", isActive && "text-beacon")} />
                    <span className="font-medium">{label}</span>
                    <span className="ml-auto font-mono text-[10px] text-fg-faint">{code}</span>
                  </>
                )}
              </NavLink>
            ))}
        </nav>

        {/* Live perimeter status — the platform's whole promise, kept in view. */}
        <div className="well mx-3 mb-3 px-3 py-2.5">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-jade/70" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-jade" />
            </span>
            <span className="font-mono text-[10px] uppercase tracking-eyebrow text-jade">
              Air-gapped
            </span>
          </div>
          <div className="mt-1 font-mono text-[10px] tracking-wider text-fg-faint">
            zero egress · on-premise
          </div>
        </div>

        <div className="border-t border-edge/12 p-3">
          <div className="flex items-center gap-3 px-1 py-1">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-beacon/10 font-mono text-xs font-semibold text-beacon ring-1 ring-inset ring-beacon/25">
              {initials(user?.username ?? "?")}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-medium text-fg">{user?.username}</div>
              <div className="truncate font-mono text-[10px] uppercase tracking-wider text-fg-faint">
                {roles.join(" · ") || "—"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              title="Sign out"
              className="grid h-8 w-8 place-items-center rounded-md text-fg-faint transition-colors hover:bg-raise hover:text-fg"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-h-screen flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex items-center justify-between border-b border-edge/12 bg-slab/80 px-4 py-3 backdrop-blur md:hidden">
          <div className="flex items-center gap-2.5">
            <SovereignMark className="h-6 w-6 text-beacon" />
            <span className="font-mono text-sm font-semibold tracking-[0.28em] text-fg">AEGIS</span>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="font-mono text-[11px] uppercase tracking-eyebrow text-fg-dim"
          >
            Sign out
          </button>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
