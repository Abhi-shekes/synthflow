import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Projects",
    // Re-declared because a plain string title stops the root template from
    // reaching this segment's children.
    template: "%s · SynthFlow",
  },
  description: "Every system you are modelling.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
