"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AuthScene } from "@/components/auth/auth-scene";
import { Mark } from "@/components/brand/mark";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useTilt } from "@/lib/motion";
import { useAuthStore } from "@/lib/store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

interface FormValues {
  email: string;
  password: string;
}

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>();

  const { ref: tiltRef, tiltProps } = useTilt<HTMLDivElement>();
  const shakeRef = useRef<HTMLDivElement | null>(null);

  const sso = useQuery({
    queryKey: ["sso-status"],
    queryFn: () => api.ssoStatus(),
    // Unauthenticated by design — it says only that an option exists, which
    // the button using it would say anyway.
    staleTime: 5 * 60 * 1000,
  });

  // The SSO callback lands here with the access token in the URL
  // *fragment*. A fragment is never sent to a server, so the credential
  // stays out of access logs, proxy logs and Referer headers — which the
  // query string would not. The refresh token doesn't travel this way at
  // all: the backend sets it as an httpOnly cookie on the callback
  // redirect itself, the same as a password login.
  useEffect(() => {
    if (typeof window === "undefined" || !window.location.hash) return;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = params.get("access_token");
    if (!accessToken) return;

    // Cleared immediately so a bookmark, a screenshot or a back-button press
    // cannot resurrect a working credential from the address bar.
    window.history.replaceState(null, "", window.location.pathname);

    api
      .me(accessToken)
      .then((user) => {
        setAuth(accessToken, user);
        router.push(user.has_onboarded ? "/projects" : "/welcome");
      })
      .catch(() => toast.error("That single sign-on session could not be completed"));
  }, [router, setAuth]);

  const mutation = useMutation({
    mutationFn: async ({ email, password }: FormValues) => {
      const { access_token } = await api.login(email, password);
      const user = await api.me(access_token);
      return { access_token, user };
    },
    onSuccess: ({ access_token, user }) => {
      setAuth(access_token, user);
      router.push(user.has_onboarded ? "/projects" : "/welcome");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Login failed"),
  });

  // A rejected submit shakes the panel once — a "no" you feel, not just
  // read. The panel itself keeps its own ref for pointer tilt, so the shake
  // lives on a wrapping element and composes with that transform instead of
  // fighting it for the same CSS property.
  useEffect(() => {
    if (mutation.failureCount === 0) return;
    const node = shakeRef.current;
    if (!node) return;
    node.classList.remove("sf-shake");
    void node.offsetWidth;
    node.classList.add("sf-shake");
  }, [mutation.failureCount]);

  return (
    <AuthScene>
      <div ref={shakeRef}>
        <Panel ref={tiltRef} {...tiltProps} className="w-full sf-rise">
          <PanelBody className="flex flex-col gap-5 py-6">
            {/* The mark, at the one moment the product introduces itself. */}
            <Mark className="mx-auto size-8" />
            <div className="text-center">
              <h1 className="font-display text-lg font-bold tracking-tight">Sign in</h1>
              <p className="mt-0.5 text-xs text-ink-dim">Welcome back to SynthFlow</p>
            </div>
            <div>
              <form
                className="flex flex-col gap-4"
                onSubmit={handleSubmit((values) => mutation.mutate(values))}
              >
                <div className="flex flex-col gap-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    className="focus-visible:border-[var(--t-string)] focus-visible:ring-[var(--t-string)]/25"
                    {...register("email", { required: "Email is required" })}
                  />
                  {errors.email && (
                    <p className="text-xs text-sev-crit">{errors.email.message}</p>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    className="focus-visible:border-[var(--t-enum)] focus-visible:ring-[var(--t-enum)]/25"
                    {...register("password", { required: "Password is required" })}
                  />
                  {errors.password && (
                    <p className="text-xs text-sev-crit">{errors.password.message}</p>
                  )}
                </div>
                <Button
                  type="submit"
                  disabled={mutation.isPending}
                  className="mt-2 gap-1.5"
                >
                  {mutation.isPending && <Loader2 className="size-3.5 animate-spin" />}
                  {mutation.isPending ? "Signing in…" : "Sign in"}
                </Button>
              </form>
              {sso.data?.enabled && (
                <>
                  <div className="my-4 flex items-center gap-3">
                    <span className="h-px flex-1 bg-line" />
                    <span className="text-xs text-ink-faint">or</span>
                    <span className="h-px flex-1 bg-line" />
                  </div>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      // A full navigation, not fetch: the identity provider
                      // needs the browser itself, so it can show its own login
                      // and reuse a session the user may already have there.
                      // The rule below assumes an internal Next.js route;
                      // API_URL is the backend, a different origin, and a
                      // router push cannot leave the app.
                      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
                      window.location.href = `${API_URL}/api/v1/auth/sso/login`;
                    }}
                  >
                    Sign in with single sign-on
                  </Button>
                </>
              )}
              <p className="mt-4 text-center text-xs text-ink-dim">
                No account?{" "}
                <Link href="/signup" className="underline underline-offset-4">
                  Sign up
                </Link>
              </p>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </AuthScene>
  );
}
