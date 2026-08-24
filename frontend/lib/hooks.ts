"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import type { User } from "@/lib/types";

/** Whether the one-time silent-refresh attempt on app load has finished.
 * False on the server and on first client render, true once
 * `app/providers.tsx` has tried `/auth/refresh` against the httpOnly
 * refresh cookie and either succeeded or given up. */
export function useAuthReady() {
  return useAuthStore((s) => s.authReady);
}

/** Waits for the silent-refresh attempt before deciding to redirect, so a
 * logged-in user with a live refresh cookie isn't bounced to /login on a
 * hard refresh just because the in-memory access token hasn't been
 * re-fetched yet. */
export function useRequireAuth() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const ready = useAuthReady();

  useEffect(() => {
    if (ready && !accessToken) router.replace("/login");
  }, [ready, accessToken, router]);

  return ready ? accessToken : undefined;
}

/** "guided" (the default for every new account) hides Behaviour/Distortion/
 * advanced-Delivery depth and the less-common nav sections; "advanced" is
 * the full instrument panel. */
export function useViewMode(): "guided" | "advanced" {
  return useAuthStore((s) => s.user?.ui_mode ?? "guided");
}

/** Flips the mode, optimistically and immediately — the toggle should never
 * wait on a round trip — then persists it so it survives a refresh or a
 * different device. */
export function useSetViewMode() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: async (mode: "guided" | "advanced") => {
      if (user) setUser({ ...user, ui_mode: mode });
      return api.updateMe(accessToken!, { ui_mode: mode });
    },
    onSuccess: (updated: User) => setUser(updated),
  });
}

/** Marks the welcome flow (S4) done — called on both completion and skip, so
 * it never re-triggers. */
export function useCompleteOnboarding() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (user) setUser({ ...user, has_onboarded: true });
      return api.updateMe(accessToken!, { has_onboarded: true });
    },
    onSuccess: (updated: User) => {
      setUser(updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
