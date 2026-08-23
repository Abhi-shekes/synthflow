import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create your account",
  description: "Start modelling a system with SynthFlow.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
