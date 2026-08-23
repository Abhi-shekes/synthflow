import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

/**
 * The home-screen icon for iOS, which will not render an SVG favicon.
 *
 * Generated rather than committed as a binary so it cannot drift from
 * `app/icon.svg` unnoticed — the two are the same four bands, and changing one
 * without the other is the usual way a mark ends up inconsistent.
 *
 * iOS applies its own rounding and drops the icon on an opaque tile, so this
 * draws a square with no corner radius and a filled ground of its own.
 */
export default function AppleIcon() {
  const bands = [
    { width: 116, color: "#63B3D9" },
    { width: 82, color: "#4FAE9C" },
    { width: 116, color: "#E8925C" },
    { width: 58, color: "#E7B45C" },
  ];

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 12,
          padding: 32,
          background: "#0A0D13",
        }}
      >
        {bands.map((band) => (
          <div
            key={band.color}
            style={{ width: band.width, height: 22, borderRadius: 8, background: band.color }}
          />
        ))}
      </div>
    ),
    size
  );
}
