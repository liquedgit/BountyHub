# BountyHub — Backlog

Each task is independently implementable (~15 tool turns incl. tests) and branches from
`main`.

```
1  frontend foundation (UI kit, API client) ─┬─► 3  app shell + auth pages ───────┐
                                             ├─► 4  programs ─────────────────────┤
                                             ├─► 5  findings + notes ─────────────┤
                                             ├─► 7  settings (AI provider) ───────┼─► 9  rebuild, verify
2  backend read endpoints ──┬────────────────┼─► 6  recon (needs 1 and 2) ────────┤
                            └────────────────┴─► 8  overview (needs 1 and 2) ─────┘
```

1 and 2 start now, in parallel. 3–8 run in parallel once their prerequisites are merged.

Rules for tasks 1–8 (spec §4 "UI system", §8 "Working in parallel on one host"):
- Never `up`, `down`, `build` or wipe the `bountyhub` stack, never touch the main
  checkout's `infra/.env`, never push. Task 9 is the only one that touches the stack.
- File ownership, so parallel branches merge cleanly. Only task 1 edits
  `frontend/package.json`, `package-lock.json`, `src/lib/api.ts`, `src/lib/types.ts`,
  `src/components/ui/*`, `src/components/common/*`, `globals.css`, `tailwind.config.ts`.
  Tasks 3–8 edit only the files named in their section; a missing primitive is a **new**
  file, a missing API method or type is reported in the hand-in, not patched in place.
- Frontend tasks finish with `npm test`, `npm run lint` and `npm run build` green.
- No raw `<input>`/`<button>`/`<select>` and no hard-coded colour classes in feature code.

## Done
1–16. Backend, recon pipeline, AI triage, first frontend, migrations, worker image.
17–22. Published to GitHub as `main`, stack running, `scripts/stack.sh`, `scripts/smoke_test.py`.
23–26. `/auth/status`, working sign-in, `/register` first-run page, verified and pushed.

## Open — UI and behaviour pass (spec §3 lists what is wrong today)

### 1. Frontend foundation: UI kit, shared states, one API client
Everything tasks 3–8 build on. No page redesign here; existing pages must keep working.
- Tokens: add `success`, `warning`, `info` (with `-foreground`) to `globals.css` and
  `tailwind.config.ts`. Default theme dark (`providers.tsx`), toggle kept.
- Dependencies (the only task that adds any): `@radix-ui/react-dialog`,
  `@radix-ui/react-tabs`, `sonner`.
- `components/ui/`: add textarea, select (styled native), badge (default, secondary,
  outline, success, warning, info, destructive), table, tabs, dialog, sheet, skeleton,
  toaster; make sure button has `outline`, `ghost`, `destructive` variants and an `icon`
  size. Mount the toaster in `providers.tsx`.
- `components/common/`: `PageHeader`, `EmptyState`, `ErrorState`, `ListSkeleton`,
  `ConfirmDialog`, `StatCard`, `SeverityBadge`, `StatusBadge`, `CopyButton`, `Markdown`.
  `lib/format.ts`: `formatDate`, `formatRelative`, `formatMoney(cents)`, `formatDuration`.
- `lib/api.ts`: one `ApiError(status, message, body)` with the message from `detail`
  (string or validation list), `errorMessage(err)`, 401 → `/login?next=<path>` except on
  the login call. `lib/api-client.ts` re-exports from it; `features/auth/api.ts` keeps
  working. Add methods for the whole contract in spec §4: `api.targets`,
  `api.programs.scopeCheck`, `api.recon.list(programId?)`, `api.dashboard.summary`,
  `api.settings.getAI/updateAI`, `api.triage.run(jobId)`.
- `lib/types.ts`: `Target`, `AISettings`, `AISettingsUpdate`, `DashboardSummary`,
  `ScopeCheckResult`; `created_at`/`updated_at` on program, target, finding, note;
  `triage_label`, `triage_reason` on `ReconAsset`.
- `providers.tsx`: React Query defaults (`refetchOnWindowFocus: false`, `retry: 1`) and a
  mutation-cache `onError` that toasts `errorMessage(err)` unless `meta.silent` is set.
- `ProgramScoped` / `ProgramSelect`: selection in `?program=<id>` and `localStorage`,
  auto-select when there is one program, `EmptyState` linking to `/programs` when there
  are none. `useSearchParams` needs a `<Suspense>` boundary or `npm run build` fails.
- Split `tests/features.test.tsx` into `tests/{programs,findings,notes,recon}.test.tsx`
  (same assertions) and delete it.

Tests: `tests/ui-kit.test.tsx` (ConfirmDialog confirm/cancel, EmptyState action,
SeverityBadge/StatusBadge text), `tests/api.test.ts` (message from string and list
`detail`, 401 redirect, 204), `tests/program-scoped.test.tsx` (reads `?program`,
auto-selects a single program, empty state).

### 2. Backend: scan history, dashboard summary, triage fields, timestamps
Additive only (spec §4 "HTTP API"); no migration is needed, the columns exist.
- `GET /recon/scans?program_id=&limit=`: `ReconJobRepository.list(program_id=None,
  limit=20)` newest first, through `ReconService`; `limit` 1–100.
- `ReconAssetRead` gains `triage_label` (`ai_label`) and `triage_reason` (`ai_reason`).
- `TargetRead`, `FindingRead`, `NoteRead` gain `created_at`, `updated_at`; `ProgramRead`
  gains `updated_at`.
- `GET /dashboard/summary`: new `app/api/dashboard.py`, `DashboardService`,
  `app/schemas/dashboard.py`, shape exactly as in the spec. Aggregate in SQL
  (`count`/`sum`/`group by`), not by loading rows. Requires auth. Register the router in
  `main.py` by adding a line.

Tests: `tests/test_dashboard.py` (empty database → zeros and every enum key present;
seeded data → counts, `open`, `payout_cents_paid`, recent lists ordered and capped at 5,
`ai_configured` false then true), list-scans ordering/filter/limit in the recon tests,
asset fields after triage, timestamps in `test_bounty_api.py`, and both new routes in
`test_route_protection.py` (401 without the cookie). `pytest` and `ruff check .` green.

### 3. App shell: sidebar, mobile navigation, header, auth pages  (after 1)
Files: `app/layout.tsx`, `app/(dashboard)/layout.tsx`, new `app/(dashboard)/loading.tsx`
and `error.tsx`, new `app/not-found.tsx`, `components/layout/*`, `features/dashboard/nav.ts`,
`app/login/page.tsx`, `app/register/page.tsx`, `components/auth/*`.
- Sidebar: brand mark, nav with Settings pinned at the bottom (`/settings`, built by
  task 7), parent highlighted on nested routes, `aria-current="page"`.
- Below `md`: top bar with a menu button opening the same nav in a sheet that closes on
  navigation. Today there is no navigation at all on a phone.
- Header: signed-in email (`/auth/me`), theme toggle, sign out. Content in a centred
  `max-w-6xl` container with consistent padding.
- Route-level loading skeleton, error boundary with retry, and a 404 page.
- Auth pages: same card, brand and tokens; pending state on submit; show/hide password.
  The auth flow, redirects and existing auth tests stay as they are.
- `metadata.title` template `"%s · BountyHub"` in the root layout.

Tests: `tests/shell.test.tsx` (nested route highlights its parent, menu button opens the
nav and it lists every item, email shown). Existing auth and middleware tests untouched.

### 4. Programs: list, detail, scope and targets  (after 1)
Files: `app/(dashboard)/programs/**`, `components/programs/*` (except `ProgramSelect`),
`tests/programs.test.tsx`.
- List: `PageHeader` with "New program" opening a dialog (name, platform, URL, reward
  info: URL and reward info cannot be entered anywhere today), search, rows with
  platform badge, reward info and created date, skeleton / empty / error states.
- Detail: back link, edit dialog, delete with confirm (then `/programs`), links to
  `/findings`, `/notes`, `/recon` with `?program=<id>`. Render `program.url` as a link
  only when it is `http(s)`, with `target="_blank" rel="noopener noreferrer"`.
- Scope tab: in and out rules grouped, type badge, add form with one line of help per
  type (domain is exact, `*.example.com` does not cover the apex, IP or CIDR, URL path
  prefix), delete with confirm, and a "test a host" box on `scope-check` showing the
  verdict and reason.
- Targets tab: list, add, edit, delete (value, description). The API exists, the UI
  does not.

Tests: create with all four fields, edit, delete confirm, add/remove rule, scope-check
result shown, target CRUD, a `javascript:` URL is not rendered as a link.

### 5. Findings and notes  (after 1)
Files: `app/(dashboard)/findings/*`, `app/(dashboard)/notes/*`, `components/findings/*`,
`components/notes/*`, `tests/findings.test.tsx`, `tests/notes.test.tsx`.
- Findings: board by status kept, columns scroll horizontally on small screens; cards
  with `SeverityBadge`, payout and updated time; totals strip (count, open, paid total);
  severity filter; "New finding" dialog; clicking a card opens a dialog to edit title,
  description (markdown), severity, status, target and payout (dollars in, cents out,
  validated), and to delete with confirm.
- Notes: searchable list with updated time; editor with Edit/Preview tabs (side by side
  on wide screens) using `Markdown`; unsaved-changes indicator, Save disabled when
  clean, Ctrl/Cmd+S saves, a confirm before switching away from unsaved edits, delete
  with confirm, optional link to a finding of the same program.

Tests: existing assertions kept; plus edit and delete a finding, payout validation,
severity filter, note dirty state and save, delete confirm, finding link saved.

### 6. Recon: launcher, history, progress and results  (after 1, 2)
Files: `app/(dashboard)/recon/*`, `components/recon/*`, `tests/recon.test.tsx`.
- Fix: on a 422 read `rejected_targets` from the top level of the error body and say
  which targets were out of scope (and correct the test's mock to the real shape).
- Fix: scores are 0–100. Show an integer; 70 and up high, 40–69 medium, below low,
  with the label as text, not colour alone.
- Launcher: targets textarea with a parsed-count hint, the scope note, pending state.
- History: the program's scans from `GET /recon/scans?program_id=` with status badge,
  target count and relative time; the selected scan lives in `?scan=<id>` so a reload
  keeps it; a newly launched scan is selected. Polling as today, stops on a final state.
- Selected scan: stage stepper (scope → subfinder → httpx → js_crawler →
  secret_scanner → triage), started/finished/duration, rejected targets, `notes` as
  warnings, `error` as an error block.
- Results: tabs per asset type with counts; table with value (`CopyButton`), source,
  label badge, score, reason; text filter; sorted by score; row detail showing `meta`
  (status, title, tech for hosts). Secrets show only what the API returns.
- "Re-run AI triage" on a completed scan (`POST /triage {job_id}`): 409 → "No AI
  provider configured" with a link to `/settings`; 502 → the provider's message.
- No scan is ever launched against a real host while developing or testing.

Tests: existing assertions kept with the corrected 422 shape; plus history list and
selection from `?scan`, stepper marks the current stage, score bands, filter, triage 409.

### 7. Settings page: AI provider  (after 1)
Files: new `app/(dashboard)/settings/page.tsx`, `components/settings/*`,
`tests/settings.test.tsx`.
- Provider choice (Claude Code token / OpenAI-compatible) and the fields of each:
  Claude token + model; base URL + API key + model. A "saved" / "not set" badge per
  credential from `claude_token_set` / `openai_api_key_set`.
- Credentials are write-only: password inputs, never pre-filled, and a blank one is
  omitted from the `PUT` (the backend rejects an empty string and treats a missing
  field as unchanged). Help text: the token comes from `claude setup-token`.
- Success toast, server message on failure, skeleton and error states.
- Account card: signed-in email and sign out.

Tests: loads and shows saved/not-set, a save with a blank secret omits it from the
request body, changing provider sends `provider`, a stored secret is never rendered.

### 8. Overview dashboard  (after 1, 2)
Files: `app/(dashboard)/page.tsx`, new `components/dashboard/*`, `tests/dashboard.test.tsx`.
- From `GET /dashboard/summary`: stat cards (programs, open findings, paid total, active
  scans), findings by severity as CSS bars (no chart library), recent findings and
  recent scans with badges and links.
- No programs yet: a getting-started checklist (create a program, add scope rules,
  configure the AI provider, run a scan) with links. `ai_configured` false: a callout
  linking to `/settings`.
- Skeleton, error with retry.

Tests: numbers and money rendered from a mocked summary, checklist on an empty summary,
AI callout only when `ai_configured` is false, error state with retry.

### 9. Rebuild, verify and report  (after 1–8)
The only task that touches the stack. Project `bountyhub` only. **Never run `reset`,
never remove the volume: the database may hold the user's account** (spec §8).
1. On `main` with 1–8 merged: `pytest`, `ruff check .`, `npm test`, `npm run lint`,
   `npm run build`. Grep `frontend/src` for leftover raw `<input`/`<button`/`<select`
   outside `components/ui` and for `bg-blue-`/`text-red-`; fix what is left.
2. Extend `scripts/smoke_test.py` with the checks added in spec §8 (`/dashboard/summary`,
   `GET /recon/scans`, `/settings` page). Standard library and `.invalid` hosts only.
3. Run the full smoke test against a throwaway dev backend (SQLite, `127.0.0.1`, spare
   port, stopped afterwards).
4. `scripts/stack.sh up` to rebuild; wait for all five services. Read `GET /auth/status`
   on the running stack. If registration is closed, run only signed-out checks there
   (`/login` 200, `/` redirects to `/login`, an API call without the cookie is 401) and
   do not register or sign in. If it is still open, the full smoke test with throwaway
   credentials may run, followed by `scripts/stack.sh reset --yes` and proof that
   `select count(*) from users` is 0.
5. Commit on `main`. **Do not push**: the user has not asked for this round to be
   published. Report the URLs from `scripts/stack.sh urls`, the smoke output, what was
   and was not checked in a real browser, and that `main` is ahead of `origin/main`.
