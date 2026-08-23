# Simplicity & Onboarding TODO

Working checklist for the simplicity/onboarding track. For the reasoning —
why progressive disclosure over forked pages, why the glossary is the load
-bearing dependency, what's deliberately deferred — see
[SIMPLICITY_PLAN.md](SIMPLICITY_PLAN.md). This file is only what's done, in
flight, and next.

Phases are lettered `S1`–`S5` so they never collide with `ROADMAP.md`'s
numbered backend phases or `UI_UPGRADE_PLAN.md`'s `U1`–`U5`.

## Status at a glance

| Phase | What | State |
|---|---|---|
| **S1** | Glossary + plain-language copy pass | **done** |
| **S2** | Guided/Advanced mode | **done** |
| **S3** | Context help panel, empty states, error copy | **done** (empty-state pass partial — see notes) |
| **S4** | First-run onboarding | **done** |
| **S5** | Learn page | **done** |

**Ordering constraint: S1 before everything else.** Every later phase reads
copy from the glossary rather than writing its own.

---

## S1 — Glossary + copy pass — done

- [x] `lib/glossary.ts` — 20 terms (k-anonymity, l-diversity,
      quasi-identifier, event trigger, trend, geo route, lookup attachment,
      error injection, formula, rule, workflow, each delivery protocol, PII,
      null rate), typed as `Record<GlossaryId, GlossaryEntry>` so every
      entry is uniform even though only some carry an `example`.
- [x] `components/help/term.tsx` — `<Term id="...">`, click-to-toggle info
      affordance (not hover-only — hover has no touch equivalent), reads
      `lib/glossary.ts`.
- [x] Applied `<Term>` at: the privacy panel (quasi-identifiers, k, l), all
      seven delivery protocol titles, and the six Behaviour/Distortion
      stratum panel titles on the entity page.

## S2 — Guided / Advanced mode — done

- [x] `ui_mode` (`"guided" | "advanced"`, default `"guided"`) and
      `has_onboarded` columns on `users`, migration
      `a1b2c3d4e5f6_add_ui_mode_and_onboarding_to_users`, `PATCH
      /api/v1/auth/me`. `useAuthStore.setUser` + `useViewMode`/
      `useSetViewMode`/`useCompleteOnboarding` in `lib/hooks.ts`.
      `components/shell/mode-toggle.tsx` — two-state control in the rail
      (desktop) and header (mobile).
- [x] Rail: Guided defers `Data & jobs` / `Governance` / `Monitor` /
      `Organizations` / `API keys` behind a **"More"** disclosure — named
      "More", not "Advanced", to avoid colliding with the mode toggle's own
      "Advanced" label (caught by manual testing: the two controls being
      both called "Advanced" was genuinely ambiguous). Clicking a
      currently-active advanced link still shows it, even collapsed.
- [x] Entity page: `Stratum` (`components/strata/stratum.tsx`) takes an
      optional `hasContent` — collapses to a one-line "Add {stratum}"
      affordance in Guided mode only when `id !== "shape"` and the stratum
      genuinely has nothing configured yet, so a stratum someone already
      populated (e.g. a starter template's pre-built rules/trends) is never
      hidden by a later mode change.
- [x] Delivery stratum: `hasContent` forced `true` on its outer `Stratum` —
      Generate/Download and REST output lead unconditionally, regardless of
      mode. The other five protocols (WebSocket, Kafka, RabbitMQ, webhook,
      MQTT, plugin) collapse via a new, more granular
      `components/help/advanced-section.tsx`, reused for any future
      sub-section split. (Caught by manual testing: without the forced
      `hasContent`, the *whole* Delivery stratum — including REST — was
      hidden behind a generic "Add delivery" button, which the plan never
      intended.)
- [x] System Map: Guided defaults to the list view; a segmented Map/List
      toggle in the header (desktop only — phones always get the list, per
      the existing sub-`md` fallback). `null`-until-touched override state,
      so flipping it once "sticks" for the rest of the visit without
      persisting a permanent preference.

## S3 — Helper layer — done (empty-state pass partial)

- [x] Context help panel — `components/help/help-panel.tsx` +
      `help-content.ts`: "?" in the header, route-pattern-matched static
      content (what the page is for, common actions, glossary links for
      that page). Links to `/learn`.
- [x] Error-translation map — `lib/friendly-error.ts`, wired into all 80
      `toast.error(error.message || "...")` call sites across 19 files
      (scripted, verified with `tsc`/`lint`/`build`). Six pattern categories
      (bad regex, duplicate name, wrong credentials, connection failure,
      not-found, expired session); anything unmatched still falls back to
      the raw message exactly as before.
- [~] Empty-state pass — not done as a dedicated sweep. `PanelEmpty`
      already existed and follows the right shape; a full audit of every
      "no X yet" string across the app for the three-part (what/why/CTA)
      pattern is real remaining work, left for a follow-up pass rather than
      rewritten wholesale here.

## S4 — Onboarding — done

- [x] `has_onboarded` flag (see S2) — set via `useCompleteOnboarding`,
      called on both finishing and skipping the welcome flow.
- [x] Welcome flow — `app/welcome/page.tsx`. Built as **one screen**, not
      three: a starter template, "Start blank", and "Import an existing
      schema" are presented together rather than gated behind a first
      "what are you here for?" question, since every path leads to the same
      next step regardless of the answer — a separate first screen would
      only add a click. `login`/`signup` route to `/welcome` instead of
      `/projects` when `!user.has_onboarded`.
- [x] Seeding an example project happens **from the welcome flow's own
      actions** (pick a template / start blank / import), not automatically
      on `POST /auth/signup` as originally planned — an unconditional
      backend seed broke 5 existing tests' assumption that a fresh signup
      has zero projects, and would equally surprise any script or
      integration calling the signup API directly. Doing it client-side,
      only when someone actually goes through onboarding, has no such
      blast radius.
- [x] Coach marks — `components/onboarding/coach-mark.tsx`. One banner on
      the System Map, one on the entity page (naming all four strata,
      rather than four separately-positioned marks — the System Map is a
      pan/zoom canvas and the strata scroll independently, so a
      DOM-anchored spotlight tooltip would be fragile across both; an
      inline `Panel`-based banner says the same thing without pinning to a
      moving target). Read via `useSyncExternalStore`, not `useEffect` +
      `setState`, per this codebase's existing convention
      (`useAuthHydrated`) and to satisfy the `react-hooks/set-state-in-effect`
      lint rule already enforced here.
- [x] Getting-started checklist — `components/onboarding/getting-started-card.tsx`
      + `lib/checklist.ts`. Real per-viewer progress via `localStorage`
      flags set at the actual success handlers (entity created, rows
      generated, a REST output created as the delivery proxy), not a
      backend aggregate. Dismissible; hides itself once the three required
      steps are done.

## S5 — Learn page — done

- [x] `app/learn/page.tsx` — every route's help topic plus all 20 glossary
      terms, one page. Linked from the S3 help panel and reads the same
      `help-content.ts` / `lib/glossary.ts` as everything else.

---

## Explicitly deferred

- **AI "ask in plain English" helper** — depends on `ROADMAP.md` Phase 6
  (BYO-LLM), which is not started. Do not build a second, uncoordinated AI
  integration ahead of it.

## Acceptance checks, every phase

- [x] `npx tsc --noEmit` and `npm run lint` clean.
- [x] `npm run build` clean; backend `pytest` clean (691 passed, 5 skipped).
- [x] Both modes (Guided/Advanced) checked live in a browser against the
      project's own `docker-compose` dev stack — not just typecheck. Caught
      and fixed two real bugs this way (see S2 notes): Delivery
      over-collapsing, and the "More"/"Advanced" naming collision.
- [ ] Both themes checked — only dark was exercised during manual testing;
      light theme not separately re-verified for the new surfaces.
- [ ] Nothing in Guided mode is a dead end — every hidden surface stays one
      click away via the rail's "More" entry point. True for nav links;
      `prefers-reduced-motion` on the coach marks and empty-state audit
      (S3) were not separately re-checked.
