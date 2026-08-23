import type { MetadataRoute } from "next";

/**
 * Web app manifest.
 *
 * Present so an installed or pinned SynthFlow gets its own name, icon and
 * ground colour instead of a browser-supplied screenshot and the page title.
 * `display: "standalone"` because the product is a tool people keep open, not a
 * document they visit.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SynthFlow — synthetic data simulation",
    short_name: "SynthFlow",
    description:
      "Design realistic data. Simulate real-world behavior. Deliver it anywhere.",
    start_url: "/projects",
    display: "standalone",
    // Both drawn from the dark palette: the app defaults to dark, so a light
    // splash would flash the wrong ground before the first paint.
    background_color: "#0A0D13",
    theme_color: "#0A0D13",
    categories: ["developer", "productivity", "utilities"],
    icons: [
      { src: "/icon.svg", type: "image/svg+xml", sizes: "any", purpose: "any" },
      { src: "/apple-icon", type: "image/png", sizes: "180x180", purpose: "any" },
    ],
  };
}
