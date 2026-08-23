import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Governance",
  description: "Version history, access and the audit log.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
