import { login as apiLogin, logout as apiLogout } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";

export function useAuth() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const roles = useAuthStore((s) => s.roles);
  const setSession = useAuthStore((s) => s.setSession);
  const clear = useAuthStore((s) => s.logout);

  const login = async (username: string, password: string): Promise<void> => {
    const resp = await apiLogin(username, password);
    setSession(resp.access_token, resp.refresh_token, resp.user);
  };

  const signOut = async (): Promise<void> => {
    try {
      await apiLogout();
    } catch {
      // Best effort; clear locally regardless.
    }
    clear();
  };

  return {
    user,
    roles,
    isAuthenticated: Boolean(accessToken),
    hasRole: (role: string): boolean => roles.includes(role),
    login,
    signOut,
  };
}
