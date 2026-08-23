import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "System map",
    // Same reason as app/projects/layout.tsx: data, delivery, monitor,
    // governance and entities all sit below this segment.
    template: "%s · SynthFlow",
  },
  description: "The project as a pipeline: sources, entities, destinations.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
