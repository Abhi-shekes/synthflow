import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data & jobs",
  description: "Generation runs, record stores, reference tables and connections.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
