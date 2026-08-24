import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Default position (bottom-left) sits directly on top of the app rail's
  // theme toggle (Light/Dark/System, also bottom-left), blocking clicks on
  // it in dev mode. Move the indicator out of the way instead.
  devIndicators: {
    position: "bottom-right",
  },
};

export default nextConfig;
