import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { TokenPair } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (tokens: TokenPair, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setAuth: (tokens, user) =>
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: "synthflow-auth" }
  )
);
