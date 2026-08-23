# Visual Polish TODO

Working checklist for the visual-polish track. For the reasoning — the
font-size measurements, the screenshot evidence, why color reuses the
existing systems instead of adding a new one — see
[VISUAL_POLISH_PLAN.md](VISUAL_POLISH_PLAN.md). This file is only what's
done, in flight, and next.

Phases are lettered `V1`–`V4`, distinct from `U1`–`U5` and `S1`–`S5`.

## Status at a glance

| Phase | What | State |
|---|---|---|
| **V0** | Rail bottom-controls crowding | **done** |
| **V1** | Type-scale floor | **done** |
| **V2** | Per-section color+icon identity (component) | **done** |
| **V3** | Apply V2 across project-level pages | **done** |
| **V4** | Wayfinding / arrival polish | **done** — color was sufficient, no motion added |

**Ordering constraint: V1 before V2/V3.** New header markup written against
the old type scale gets rewritten the moment V1 lands.

---

## V0 — Rail crowding — done

- [x] `components/app-shell.tsx`: Guided/Advanced toggle and theme toggle
      stacked (one per row) instead of side by side in the same ~200px
      column. Verified with a screenshot — no more wrapping/clipping.

## V1 — Type-scale floor — done

- [x] Audited every `text-[10px]` / `text-[10.5px]` / `text-[11px]` usage
      across `components/strata/*`, `components/map/*`, `app-shell.tsx`,
      the project-level pages, `components/data/*`, `record-stores-card.tsx`,
      `version-history-card.tsx`, `activity-card.tsx`, `stream-preview.tsx`,
      `mode-toggle.tsx`, and `components/help/*` (glossary/help text — real
      explanatory prose, arguably the surface where legibility matters
      most). 60 occurrences found; 48 changed, bucketed by role.
- [x] Body copy and panel descriptions (real sentences: empty-state
      messages, glossary definitions, hint text): floored at 13px
      (`text-[13px]`).
- [x] Field metadata, badges, flags, captions (type abbreviations,
      timestamps, counts): floored at 12px (`text-xs`).
- [x] Table / monospace data (the live specimen table, the record-store
      browser, the monitor cumulative-stats table, version-diff lines):
      floored at 13px (`text-[13px]`).
- [x] Eyebrows (`.eyebrow`, uppercase micro-labels) and the command
      palette's auxiliary kbd/meta hints: left alone — confirmed by the
      post-fix audit below, every remaining under-12px element is one of
      these two categories, nothing else.
- [x] Re-ran the font-size audit script against the entity page and
      project page:

      | Page | Before | After |
      |---|---|---|
      | Entity page | 65/155 (42%) | 8/155 (5%) — all 8 are eyebrows/kbd |
      | Project map (list view) | 17/53 (32%) | 4/53 (8%) |

      Verified in a browser against the running dev stack, not just by
      counting className strings.

## V2 — Per-section identity component — done

- [x] Added `--sec-data` and `--sec-governance` to `app/globals.css`
      (`:root` and `.dark`, plus `@theme inline` mappings so they're real
      Tailwind utilities). `SECTION_COLOR` in `lib/field-visual.ts`: `map` →
      `--brand`, `delivery` → `--t-string` (REST's colour in
      `OUTPUT_COLOR`), `monitor` → `--sev-ok`, `data`/`governance` → the two
      new hues.
- [x] `components/section-header.tsx` — colored icon badge + dot + eyebrow +
      H1 + description + optional action slot, generalizing `Stratum`'s
      header pattern up from the entity page.
- [x] `Panel`'s `tone="marked"` applied as the hero-panel treatment on every
      section page (added an `accent` passthrough prop to `JobsCard` and
      `ShareProjectCard`, whose Panels live inside the component rather than
      the page).
- [x] Rail: `NavItem` gained an optional `section` field; `RailLink`'s
      active-state icon colour now follows `SECTION_TEXT_CLASS[section]`
      instead of a uniform `text-brand`. Settings/workspace links (no
      section assigned) keep the brand colour, unchanged.

## V3 — Apply across project-level pages — done

- [x] System Map (`app/projects/[projectId]/page.tsx`) — brand/gold
- [x] Data & jobs (`app/projects/[projectId]/data/page.tsx`) — new cyan
- [x] Delivery (`app/projects/[projectId]/delivery/page.tsx`) — blue
      (existing REST accent already used per-protocol below it)
- [x] Monitor (`app/projects/[projectId]/monitor/page.tsx`) — green
- [x] Governance (`app/projects/[projectId]/governance/page.tsx`) — new
      slate
- [x] Settings pages (`api-keys`, `organizations`, `activity`) — given the
      same slate as Governance (all three are access/administration
      concerns) rather than three more new hues. `api-keys` and
      `organizations` still use the pre-U1–U5 `Card` component for their
      body content — out of scope here (a `Card` → `Panel` migration is a
      separate, larger job); only their headers were brought up to parity.
- [x] Verified in both themes and in a browser — screenshots confirm all
      six pages are now immediately distinguishable by colour, not just by
      the words in the heading.

## V4 — Wayfinding polish — done

- [x] Re-evaluated after V3 shipped, per the plan's instruction to check
      before adding motion: side-by-side screenshots of System Map → Data →
      Delivery → Monitor → Governance now show a distinct icon-badge colour
      on every page, which reads as "you moved somewhere" on its own.
      **Conclusion: no arrival transition added.** Consistent with
      `UI_UPGRADE_PLAN.md`'s motion budget — the sixth entry has to be
      argued for, and color already did the job the plan set out to check.

---

## Acceptance checks, every phase

- [x] `npx tsc --noEmit` and `npm run lint` clean.
- [x] Font-size audit script shows the under-12px share dropping on the
      entity page and project page, not just "looks bigger" — 42%→5% and
      32%→8% respectively, with every remaining under-12px element being a
      deliberately-untouched eyebrow or kbd hint.
- [x] Both themes checked on every changed surface — dark throughout
      development, light re-verified on the Data page (identical treatment
      applies to the other four; the token system is what's shared, not
      per-page CSS).
- [x] Verified in a browser against the running dev stack, not only by
      typecheck — screenshots for every phase, plus two real bugs (Delivery
      over-collapsing, "More"/"Advanced" naming collision — both from the
      prior SIMPLICITY_PLAN.md work, not this track) were never introduced
      here; this track's own changes were clean on first browser check.
