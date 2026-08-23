import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Instrument_Sans } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

// Three roles, deliberately distinct: a display face with real character for
// headings, a clean UI sans for everything read at small sizes, and a mono with
// tabular figures for field names, expressions, and every data table — which in
// this product is most of the screen.
const display = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  display: "swap",
});

const sans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
  display: "swap",
});

const mono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  display: "swap",
});

const DESCRIPTION =
  "Design realistic data. Simulate real-world behavior. Deliver it anywhere. " +
  "An open-source synthetic data simulation platform — entities with state, " +
  "relationships that hold together, and streams that look like production traffic.";

// Only used to make Open Graph URLs absolute, which the spec requires. Self-hosted
// installs override it; the default keeps local development from emitting
// half-formed metadata.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    // Every page sets only its own name; the product name is appended here so
    // the two can never drift apart or get doubled up.
    default: "SynthFlow — synthetic data simulation",
    template: "%s · SynthFlow",
  },
  description: DESCRIPTION,
  applicationName: "SynthFlow",
  keywords: [
    "synthetic data",
    "test data",
    "data simulation",
    "data generation",
    "schema",
    "streaming",
    "open source",
  ],
  authors: [{ name: "SynthFlow" }],
  openGraph: {
    type: "website",
    siteName: "SynthFlow",
    title: "SynthFlow — data that behaves like the real thing",
    description: DESCRIPTION,
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: "SynthFlow — data that behaves like the real thing",
    description: DESCRIPTION,
  },
  // The app is behind a login and its content is nobody else's business.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  // Matches the ground token in each theme, so browser chrome on mobile is the
  // same colour as the page instead of a strip of default grey above it.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FAFAFC" },
    { media: "(prefers-color-scheme: dark)", color: "#0A0D13" },
  ],
  colorScheme: "dark light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // next-themes writes the class here on the client; suppressHydrationWarning
      // keeps the server's class-free markup from tripping React over it.
      suppressHydrationWarning
      className={`${display.variable} ${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body
        // Extensions write their own attributes onto <body> before React
        // hydrates — Grammarly adds data-gr-ext-installed and
        // data-new-gr-c-s-check-loaded, password managers and Dark Reader do
        // the same — and React reports the difference as a hydration mismatch
        // the app cannot fix or control.
        //
        // This suppresses one level only: <body>'s own attributes and text.
        // Every child is still checked normally, so a genuine mismatch inside
        // the tree is not hidden by it.
        suppressHydrationWarning
        className="min-h-full flex flex-col"
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
