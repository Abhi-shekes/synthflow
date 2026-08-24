"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Mark } from "@/components/brand/mark";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

interface FormValues {
  email: string;
  password: string;
}

export default function SignupPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>();

  const mutation = useMutation({
    mutationFn: async ({ email, password }: FormValues) => {
      await api.signup(email, password);
      const { access_token } = await api.login(email, password);
      const user = await api.me(access_token);
      return { access_token, user };
    },
    onSuccess: ({ access_token, user }) => {
      setAuth(access_token, user);
      router.push(user.has_onboarded ? "/projects" : "/welcome");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Sign up failed"),
  });

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <Panel className="w-full max-w-sm">
        <PanelBody className="flex flex-col gap-5 py-6">
          {/* The mark, at the one moment the product introduces itself. */}
          <Mark className="mx-auto size-8" />
          <div className="text-center">
            <h1 className="font-display text-lg font-bold tracking-tight">Create an account</h1>
            <p className="mt-0.5 text-xs text-ink-dim">Start modelling a system</p>
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
                autoComplete="new-password"
                {...register("password", {
                  required: "Password is required",
                  minLength: { value: 12, message: "At least 12 characters" },
                })}
              />
              {errors.password && (
                <p className="text-xs text-sev-crit">{errors.password.message}</p>
              )}
            </div>
            <Button type="submit" disabled={mutation.isPending} className="mt-2">
              {mutation.isPending ? "Creating account…" : "Sign up"}
            </Button>
          </form>
          <p className="mt-4 text-center text-xs text-ink-dim">
            Already have an account?{" "}
            <Link href="/login" className="underline underline-offset-4">
              Sign in
            </Link>
          </p>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
