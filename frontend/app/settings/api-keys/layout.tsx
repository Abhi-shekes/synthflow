import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API keys",
  description: "Machine access for CI and scripts.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
