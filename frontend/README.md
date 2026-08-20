This is the SynthFlow web UI — a [Next.js](https://nextjs.org) app (App Router,
TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Hook Form).

## Getting Started

```bash
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL if the backend isn't on :8001
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend must be running
(see `../backend/README.md` or `docker compose up -d` from the repo root) —
signup/login and everything past the landing page depend on it.

## Layout

```
app/
  page.tsx                                landing page
  login/, signup/                         auth
  projects/                               project list + create
  projects/[projectId]/                   entity list + create
  projects/[projectId]/entities/[entityId]/  field builder + generate
components/
  ui/                                     shadcn/ui primitives
  app-shell.tsx, add-field-dialog.tsx     app-specific components
lib/
  api.ts      typed fetch client for the backend
  store.ts    zustand auth store (persisted to localStorage)
  hooks.ts    useRequireAuth() route guard
  types.ts    shared types mirroring the backend schemas
```

## Build

```bash
npm run build
npm run lint
```
