"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthStore } from "@/lib/store";

/** Waits for the persisted auth store to rehydrate before deciding to redirect,
 * so a logged-in user isn't bounced to /login on a hard refresh. All access to
 * the persist API happens inside effects so this never runs during SSR/build
 * prerendering, where `useAuthStore.persist` touching localStorage would throw. */
export function useRequireAuth() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true);
      return;
    }
    return useAuthStore.persist.onFinishHydration(() => setHydrated(true));
  }, []);

  useEffect(() => {
    if (hydrated && !accessToken) router.replace("/login");
  }, [hydrated, accessToken, router]);

  return hydrated ? accessToken : undefined;
}
