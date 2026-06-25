import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { AuditPage } from "@/pages/AuditPage";
import { ChatPage } from "@/pages/ChatPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { EvalPage } from "@/pages/EvalPage";
import { LoginPage } from "@/pages/LoginPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

function NavBar(): JSX.Element {
  const { user, roles, signOut } = useAuth();
  const isAdmin = roles.includes("admin");
  const isAuditor = roles.includes("compliance_auditor") || isAdmin;
  return (
    <nav className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 text-sm">
      <span className="font-semibold text-slate-800">Aegis RAG</span>
      <Link to="/chat" className="text-slate-600 hover:text-slate-900">
        Chat
      </Link>
      <Link to="/documents" className="text-slate-600 hover:text-slate-900">
        Documents
      </Link>
      {isAuditor && (
        <Link to="/audit" className="text-slate-600 hover:text-slate-900">
          Audit
        </Link>
      )}
      {isAdmin && (
        <Link to="/eval" className="text-slate-600 hover:text-slate-900">
          Eval
        </Link>
      )}
      <div className="ml-auto flex items-center gap-3">
        <span className="text-slate-500">{user?.username}</span>
        <button type="button" onClick={() => void signOut()} className="text-slate-600 hover:text-slate-900">
          Sign out
        </button>
      </div>
    </nav>
  );
}

function Protected({ children }: { children: JSX.Element }): JSX.Element {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <div className="min-h-screen bg-slate-100">
      <NavBar />
      {children}
    </div>
  );
}

export default function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/chat" element={<Protected><ChatPage /></Protected>} />
          <Route path="/documents" element={<Protected><DocumentsPage /></Protected>} />
          <Route path="/audit" element={<Protected><AuditPage /></Protected>} />
          <Route path="/eval" element={<Protected><EvalPage /></Protected>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
