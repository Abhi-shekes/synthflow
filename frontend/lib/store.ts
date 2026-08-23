import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { TokenPair } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  /** The project the rail is pointing at.
   *
   * Kept here, and persisted, so the navigation does not change shape as you
   * move around: without it the rail shows nine entries inside a project and
   * four on Projects or Settings, which reads as things appearing and
   * disappearing rather than as one stable menu. */
  lastProjectId: string | null;
  setAuth: (tokens: TokenPair, user: User) => void;
  /** Patches the cached user in place — used after `api.updateMe` so the
   * mode toggle and onboarding flag update everywhere without a refetch. */
  setUser: (user: User) => void;
  /** Swaps in a freshly refreshed access token, leaving everything else
   * untouched — `lib/api.ts` calls this after transparently refreshing an
   * expired access token, so the rest of the app never sees the 401. */
  setAccessToken: (accessToken: string) => void;
  setLastProject: (projectId: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      lastProjectId: null,
      setAuth: (tokens, user) =>
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user }),
      setUser: (user) => set({ user }),
      setAccessToken: (accessToken) => set({ accessToken }),
      setLastProject: (projectId) => set({ lastProjectId: projectId }),
      // Clears the remembered project too: the next person to sign in on this
      // machine should not find someone else's project named in the rail.
      logout: () =>
        set({ accessToken: null, refreshToken: null, user: null, lastProjectId: null }),
    }),
    { name: "synthflow-auth" }
  )
);
