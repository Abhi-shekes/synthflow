import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Activity",
  description: "Every change across the projects you can see.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
