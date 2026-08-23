import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Organizations",
  description: "Teams, members and roles.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
