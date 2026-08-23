# Visual Polish Plan

A plan for three problems found by actually looking at the running app —
screenshots and a font-size audit against the live dev stack, not a guess
from reading component code. All three survive the U1–U5 instrument-panel
redesign and the SIMPLICITY_PLAN.md Guided-mode work: none of that touched
type scale or the identity of individual pages, which is exactly where
these live.

One item from this list is already fixed — see §0. The rest is phased
`V1`–`V4` in §4.

---

## 0. Already fixed: the rail's bottom controls

`components/app-shell.tsx`'s `mt-auto` block put the Guided/Advanced toggle
and the theme toggle — two segmented controls — side by side in a single
row, in a rail column roughly 200px wide once padding is subtracted. Together
they're wider than that, so the row wrapped: "Guided" partially clipped,
"Advanced" pushed to nowhere sensible, the three theme icons crowding in
underneath. This was a regression from the Guided/Advanced work itself —
`ThemeToggle` used to be alone there and had the row to itself.

**Fix:** stacked, one control per row, instead of side by side. Screenshot
confirms it no longer wraps. Small, isolated, done — not part of the phased
work below.

---

## 1. Font legibility — measured, not assumed

A script walked every element with direct text content on two live pages and
read its *computed* `font-size`, in a real browser:

| Page | Elements under 12px | Share |
|---|---|---|
| Entity page (Strata Inspector) | 65 of 155 | **42%** |
| Project page (System Map, list view) | 17 of 53 | **32%** |
| Welcome flow | 1 of 47 | 2% |
| Signup | 0 of 11 | 0% |

The entity page alone has **20 elements rendering at 10px** and **45 at
11px** — field metadata (`required`, `unique`, null-rate flags), panel
descriptions, glossary popovers, delivery protocol detail text. The welcome
flow and signup, both built or touched most recently and outside the old
"operator instrument panel" density, are essentially clean. **The problem
is concentrated in exactly the surfaces U1–U5 built densest** — the
Strata Inspector and System Map — where `text-[10px]` and `text-[11px]`
show up dozens of times as the default for anything that isn't a heading.

This was a deliberate density choice for an "operator's instrument panel"
aesthetic (`UI_UPGRADE_PLAN.md` §2.5: "dark-first... this is an operator's
instrument, not a marketing site"), and it reads fine on a photographed
screenshot. It does not read fine as eight-plus minutes of actual use,
which is the complaint.

### Direction

Not "search and replace text-[10px]" — a floor, applied by role:

| Role | Current | Floor |
|---|---|---|
| Body copy, panel descriptions | `text-xs` (12px) / `text-[11px]` | **13px**, real line-height |
| Field metadata, badges, flags (`required`, `2% null`) | `text-[10px]`/`text-[11px]` | **12px** |
| Eyebrows / section micro-labels | `text-[11px]` uppercase | stays — all-caps tracked labels read fine smaller than prose; this is the one category where the current size is correct |
| Table data, monospace values | `text-xs` mono | **13px**, tabular figures already on |

The eyebrow exception matters: this isn't "make everything bigger," which
would just recreate the density problem one step up. It's "stop using a
size built for a five-character uppercase label on a sentence."

---

## 2. Sections don't look like different places

Screenshotted System Map, Data & jobs, Delivery, Governance, and API keys
back to back. Every one of them is the same recipe:

```
Eyebrow (11px uppercase)
H1 (24px bold)
One-line grey description
── stack of Panel components, each: small header + grey body text ──
```

The only things that differ between "a page about where data goes" and "a
page about who can access this project" are the words. There's no color,
no icon in the content itself, no structural variation — the rail's 16px
nav icon (`Database`, `Radio`, `ScrollText`, `Boxes`) is the *only* place
each section has a distinct visual identity, and it's small enough to be
functionally invisible while looking at the page itself.

This is the "no flow" complaint. Moving from System Map → Data → Delivery →
Governance doesn't feel like moving through different concerns of the
product; it feels like the same page reloading with new copy.

**The frustrating part: this system already exists and already works.**
`components/strata/stratum.tsx`'s four strata (Shape/Behaviour/Distortion/
Delivery) each carry a distinct color (`--t-string`, `--t-float`,
`--t-enum`, `--brand`) that shows up as a dot next to the eyebrow, a
left-edge accent, and the depth rail. It's exactly the right idea — it
just stops at the entity page's boundary. The System Map, Data, Delivery
(project-level), Monitor, and Governance pages never got it.

### Direction

Extend the same mechanism upward, one color+icon identity per top-level
section, reused everywhere that section appears — the rail link, the page
header, and panel accents on that page:

| Section | Suggested identity | Why |
|---|---|---|
| System Map | `--brand` (existing) | Already the map's accent on edges/nodes |
| Data & jobs | a new "data" hue, distinct from field-type teal | Pipelines/storage, not a field type |
| Delivery | `--brand` variant or the existing output-color scale (`OUTPUT_COLOR`, already built for the map's destinations) | Reuse rather than invent — `lib/field-visual.ts` already has this |
| Monitor | `--sev-ok`/live-green family | Matches "this is running" framing already used for traffic-animated edges |
| Governance | a neutral/slate accent | Deliberately calmer — audit and history, not a place you're building something |

Mechanics, reusing what already exists rather than inventing a second
system:
- A `SectionHeader` component (generalizing `Stratum`'s header) — colored
  dot + eyebrow + H1 + description, used by every project-level page.
- `Panel`'s existing `tone="marked"` (colored left edge, already built,
  currently used at most once per screen) becomes the default for the
  *first* / hero panel on each section page, colored per-section.
- Rail icons pick up the same color when active, instead of the current
  uniform `text-brand` for every active link regardless of section.

This is additive to the existing color system (`lib/field-visual.ts`,
`STRATA` in `stratum.tsx`), not a second one — every new color is defined
once and referenced by both the rail and the page.

---

## 3. What "flow" also means: wayfinding between steps

Related but distinct from §2: strata within the entity page communicate
progression well (the depth rail, the "you are here" compression). Nothing
above the entity page does. The breadcrumb (`Projects › Banking › Customer`)
is the only continuity between screens, and it's identical in every context.

### Direction, scoped small on purpose

- The welcome flow (`app/welcome/page.tsx`) is currently one screen with
  three options side by side — deliberately not stepped, per
  `SIMPLICITY_PLAN.md`. That reasoning still holds; this isn't asking to
  add steps back. What it's missing is *arrival* — landing in a freshly
  created project should feel like a handoff, not a page load. A brief,
  reduced-motion-respecting transition (the existing motion budget in
  `UI_UPGRADE_PLAN.md` §2.4 has room for exactly one more entry, if this
  earns it) is worth trying before adding any new mechanism.
- Section-to-section navigation inside a project (System Map → Data →
  Delivery → Governance) should read as lateral movement between facets of
  one thing, not as a stack of unrelated pages. §2's per-section color is
  most of this fix on its own — a colored header is also a "you moved
  somewhere" signal. Test whether that's sufficient before adding anything
  motion-based on top of it.

---

## 4. Phasing

Lettered `V1`–`V4`, distinct from `U1`–`U5` (instrument-panel rebuild) and
`S1`–`S5` (simplicity/onboarding).

| Phase | What | Depends on |
|---|---|---|
| **V1** | Type-scale floor (§1) — a token pass, not a page-by-page rewrite | none |
| **V2** | Per-section color+icon identity (§2) — `SectionHeader`, extend `Panel`'s `marked` tone as default hero treatment | V1 (new headers use the corrected type scale from the start) |
| **V3** | Apply V2 to every project-level page: System Map, Data, Delivery, Monitor, Governance | V2 |
| **V4** | Wayfinding polish (§3) — arrival transition, re-evaluate after V3 ships whether anything beyond color is still needed | V3 |

**V1 first, alone.** Every subsequent phase writes new header/panel markup;
writing it against the old type scale means rewriting it again in V1's
wake. Same ordering logic as `UI_UPGRADE_PLAN.md`'s U1: foundation before
anything that builds on it.

## 5. Tradeoffs recorded

- **A floor by role, not a global size bump.** Uniformly bumping every
  `text-[10px]`/`text-[11px]` would re-fatten the eyebrows and badges that
  are correctly sized today, recreating a version of the density problem.
  Costs a slightly more involved token pass; worth it.
- **Reuse `lib/field-visual.ts` / `OUTPUT_COLOR` / `STRATA` colors for
  section identity rather than a new palette.** A second color system next
  to the one that already exists is exactly the kind of drift this plan is
  trying to remove. Some sections (Data, Governance) need a genuinely new
  hue since nothing existing fits; those get added to the *same* token
  file, not a new one.
- **No new motion mechanism proposed before testing whether color alone
  fixes the "no flow" complaint.** `UI_UPGRADE_PLAN.md`'s motion budget is
  deliberately tight (§2.4, "adding a sixth means arguing for it"); V4 is
  written to check first rather than assume a transition is needed.
