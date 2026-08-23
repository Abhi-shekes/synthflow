import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Welcome",
  description: "Get started with SynthFlow.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
