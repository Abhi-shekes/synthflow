"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <Link href="/projects" className="text-lg font-semibold tracking-tight">
          SynthFlow
        </Link>
        <div className="flex items-center gap-4">
          <Link
            href="/settings/api-keys"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            API keys
          </Link>
          {user && <span className="text-sm text-muted-foreground">{user.email}</span>}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
          >
            Log out
          </Button>
        </div>
      </header>
      <main className="flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
