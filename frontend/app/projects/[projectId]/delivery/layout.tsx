import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Delivery",
  description: "Every configured output across the project.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
