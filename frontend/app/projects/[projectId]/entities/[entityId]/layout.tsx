import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Entity",
  description: "Shape, behaviour, distortion and delivery for one entity.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
