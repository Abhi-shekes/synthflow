"use client";

import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { useAuthStore } from "@/lib/store";

/** Whether the persisted auth store has finished rehydrating from localStorage.
 * False on the server and on first client render, true once rehydration completes. */
export function useAuthHydrated() {
  return useSyncExternalStore(
    (callback) => useAuthStore.persist.onFinishHydration(callback),
    () => useAuthStore.persist.hasHydrated(),
    () => false
  );
}

/** Waits for the persisted auth store to rehydrate before deciding to redirect,
 * so a logged-in user isn't bounced to /login on a hard refresh. */
export function useRequireAuth() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrated = useAuthHydrated();

  useEffect(() => {
    if (hydrated && !accessToken) router.replace("/login");
  }, [hydrated, accessToken, router]);

  return hydrated ? accessToken : undefined;
}
