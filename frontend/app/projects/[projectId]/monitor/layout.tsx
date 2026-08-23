import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Live monitor",
  description: "Throughput, active streams and error rates.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
