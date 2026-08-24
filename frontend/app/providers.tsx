"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useEffect, useRef, useState } from "react";

import { Toaster } from "@/components/ui/sonner";
import { refreshAccessToken } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

/** Tries once, on first mount, to turn a live refresh cookie into an
 * in-memory access token — see `authReady` in lib/store.ts for why this
 * replaces what zustand's own localStorage-rehydration flag used to do.
 * A ref (not a state flag) guards the one-time run: React 18 Strict Mode
 * double-invokes effects in development, and a second silent refresh
 * would just be wasted work, not a bug — but there's no reason to pay it
 * twice on every page load either. */
function AuthBootstrap() {
  const ranOnce = useRef(false);

  useEffect(() => {
    if (ranOnce.current) return;
    ranOnce.current = true;
    refreshAccessToken().finally(() => useAuthStore.getState().setAuthReady());
  }, []);

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {/* Dark by default: this is an operator's instrument, and most of what
          it shows is live data on dark ground. `enableSystem` still lets the
          OS decide for anyone who has an opinion. */}
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
        <AuthBootstrap />
        {children}
        <Toaster />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
