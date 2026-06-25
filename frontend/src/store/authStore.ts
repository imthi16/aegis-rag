// Zustand auth store (CLAUDE.md §6.18): tokens + user kept in memory.

import { create } from "zustand";

import type { UserPublic } from "@/types/api";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserPublic | null;
  roles: string[];
  setSession: (access: string, refresh: string, user: UserPublic) => void;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  roles: [],
  setSession: (access, refresh, user) =>
    set({ accessToken: access, refreshToken: refresh, user, roles: user.roles }),
  setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh }),
  logout: () => set({ accessToken: null, refreshToken: null, user: null, roles: [] }),
}));
