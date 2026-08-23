import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Learn",
  description: "SynthFlow's concepts, in plain language.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
