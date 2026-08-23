import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "SynthFlow — design realistic data, simulate real-world behavior";

/** The full field-type scale, in schema order. At card size these read as the
 * product's actual subject rather than as decoration: this is what an entity
 * looks like on the system map. */
const SCALE = [
  "#63B3D9",
  "#7FC98C",
  "#4FAE9C",
  "#B98CD9",
  "#E28A9E",
  "#D97FA8",
  "#8A93AD",
  "#E8925C",
  "#A8C05E",
  "#7F8FD9",
  "#C97FD9",
];

/**
 * The social preview card.
 *
 * Built from the same core-sample device as the mark and the map, so a shared
 * link looks like the product rather than like a generic gradient with a name
 * on it. Fonts are the platform defaults on purpose — loading Bricolage here
 * means fetching and embedding a font file per render, which is a lot of
 * machinery for a picture most people see at thumbnail size.
 */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#0A0D13",
          color: "#E2E8F2",
        }}
      >
        {/* Mark + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            <div style={{ width: 62, height: 12, borderRadius: 5, background: "#63B3D9" }} />
            <div style={{ width: 44, height: 12, borderRadius: 5, background: "#4FAE9C" }} />
            <div style={{ width: 62, height: 12, borderRadius: 5, background: "#E8925C" }} />
            <div style={{ width: 31, height: 12, borderRadius: 5, background: "#E7B45C" }} />
          </div>
          <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: -1 }}>SynthFlow</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div
            style={{
              fontSize: 68,
              fontWeight: 800,
              letterSpacing: -2.5,
              lineHeight: 1.05,
              maxWidth: 860,
            }}
          >
            Data that behaves like the real thing
          </div>
          <div style={{ fontSize: 27, color: "#8792A6", maxWidth: 800, lineHeight: 1.4 }}>
            Entities with state, relationships that hold together, rules that fire, and streams
            that look like production traffic.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 8 }}>
            {SCALE.map((hue) => (
              <div key={hue} style={{ width: 62, height: 12, borderRadius: 6, background: hue }} />
            ))}
          </div>
          <div style={{ fontSize: 21, color: "#59637A" }}>Open source · AI optional</div>
        </div>
      </div>
    ),
    size
  );
}
