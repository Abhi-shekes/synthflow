## What this changes

<!-- One or two sentences. If it closes an issue, "Closes #123". -->

## Why

<!-- The reasoning, not just the mechanics. If you considered another
     approach and rejected it, that's worth a line — this repo's history
     tries to record why things are the way they are, not only what. -->

## How it was verified

<!-- CI runs lint, format, tests (on both a core-only and a full install)
     and the Docker builds. Say what you checked beyond that — especially
     anything you exercised by hand, since a lot of this project's
     behaviour only really shows up at runtime.

     For example: "generated 50 rows through the UI and confirmed the
     workflow field reached `delivered` on ~40% of them". -->

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass in `backend/`
- [ ] `pytest` passes in `backend/`
- [ ] `npm run lint` and `npm run build` pass in `frontend/`
- [ ] New behaviour has tests
- [ ] If it changes a database model, there's an Alembic migration
- [ ] If it adds an optional dependency, it's an extra — not a core
      dependency — and `app/services/install.py` degrades cleanly without it
- [ ] Any known limitation is documented rather than left to be rediscovered
