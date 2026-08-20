"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useAuthHydrated } from "@/lib/hooks";
import { useAuthStore } from "@/lib/store";

export default function Home() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrated = useAuthHydrated();

  useEffect(() => {
    if (hydrated && accessToken) router.replace("/projects");
  }, [hydrated, accessToken, router]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-4xl font-semibold tracking-tight">SynthFlow</h1>
      <p className="max-w-md text-muted-foreground">
        Design realistic data. Simulate real-world behavior. Deliver it anywhere.
      </p>
      <div className="flex gap-3">
        <Button nativeButton={false} render={<Link href="/signup">Get started</Link>} />
        <Button
          nativeButton={false}
          variant="outline"
          render={<Link href="/login">Sign in</Link>}
        />
      </div>
    </div>
  );
}
