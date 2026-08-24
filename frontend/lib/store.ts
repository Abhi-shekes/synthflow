import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/lib/types";

interface AuthState {
  /** Held in memory only — never persisted. See `authReady` below for why
   * that's safe across a page reload. */
  accessToken: string | null;
  user: User | null;
  /** The project the rail is pointing at.
   *
   * Kept here, and persisted, so the navigation does not change shape as you
   * move around: without it the rail shows nine entries inside a project and
   * four on Projects or Settings, which reads as things appearing and
   * disappearing rather than as one stable menu. */
  lastProjectId: string | null;
  /** True once the one-time silent-refresh attempt on app load has
   * finished (success or failure). The refresh token lives in an httpOnly
   * cookie the browser attaches automatically — never in localStorage, so
   * an XSS payload can't read it — which means a page reload has no client
   * copy of the access token to reuse. `app/providers.tsx` calls
   * `/auth/refresh` once on mount and sets `accessToken` if the cookie is
   * still good; `useRequireAuth` waits for this flag before deciding
   * whether to redirect, the same role `zustand`'s own hydration flag used
   * to play when the token was still in localStorage. */
  authReady: boolean;
  setAuth: (accessToken: string, user: User) => void;
  /** Patches the cached user in place — used after `api.updateMe` so the
   * mode toggle and onboarding flag update everywhere without a refetch. */
  setUser: (user: User) => void;
  /** Swaps in a freshly refreshed access token, leaving everything else
   * untouched — `lib/api.ts` calls this after transparently refreshing an
   * expired access token, so the rest of the app never sees the 401. */
  setAccessToken: (accessToken: string) => void;
  setAuthReady: () => void;
  setLastProject: (projectId: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      lastProjectId: null,
      authReady: false,
      setAuth: (accessToken, user) => set({ accessToken, user }),
      setUser: (user) => set({ user }),
      setAccessToken: (accessToken) => set({ accessToken }),
      setAuthReady: () => set({ authReady: true }),
      setLastProject: (projectId) => set({ lastProjectId: projectId }),
      // Clears the remembered project too: the next person to sign in on this
      // machine should not find someone else's project named in the rail.
      logout: () => set({ accessToken: null, user: null, lastProjectId: null }),
    }),
    {
      name: "synthflow-auth",
      // accessToken never persists — it's re-derived from the refresh
      // cookie on every load (see `authReady` above). `authReady` itself
      // is deliberately excluded too: it must start false on every real
      // page load so the bootstrap effect always runs, not just once ever.
      partialize: (state) => ({ user: state.user, lastProjectId: state.lastProjectId }),
    }
  )
);
