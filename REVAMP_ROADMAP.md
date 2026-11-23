# SSIT QR Attendance — Revamp Roadmap

Decisions locked:

- JSON QR payload stays, extended with `student_id`.
- Jinja2 templates + static CSS/JS replace inline HTML.
- Admin credentials unchanged.
- Build in phases, verifying after each.

## Foundation

- Stop the running server before schema work; ignore `*.db-wal` / `*.db-shm`.
- Extend `database.py`: `Student.student_id` (unique), `Event` (name/date/venue/windows/status), `Attendance.event_id`, `station_id`, `client_scan_id`, `AuditLog`, `ImportBatch`, `ExportLog`, `User.disabled` / `last_login`, roles `admin` / `event_staff` / `scanner`.
- DB was scrubbed empty, so `create_all` builds the new schema; defer Alembic until real data exists.
- Make `DATABASE_URL` env-overridable for isolated tests.
- Add `templates/` (base layout + partials) and `static/css`, `static/js`, vendored icon sprite; add `jinja2` to `requirements.txt`. Convert the 7 routers from inline f-string HTML to `Jinja2Templates`, keeping them as thin route/service layers.

## Phase 1 — operational reliability

- `routers/events.py`: create/select/close events; active event in a cookie; dashboard event banner, KPI cards, recent scans, persistent scan CTA.
- One `/scan` page with check-in/check-out toggle, scanning frame, camera state machine (`starting` / `ready` / `blocked` / `offline`), translated errors with "Show details", pinned result, 1–2s confirmation state.
- Manual fallback by `student_id` plus QR-image upload decode; unify `/checkin` + `/checkout` into `POST /api/scan` (keep aliases), with duplicate/sequence validation.
- Apply the token palette, 8px spacing, 44px targets, responsive single-column mobile, reduced glow.

## Phase 2 — data confidence

- Student form: grouped fields, selects, duplicate validation, "Save and add another", QR download on create; consolidates the two duplicate `/upload-csv` handlers.
- CSV workflow: template → upload → `ImportBatch` preview with inline errors → confirm → skipped/duplicate counts + downloadable error report.
- QR management: search, multi-select, download selected/all; live view becomes a control room (KPIs, activity feed, filters, search, last-updated + WS status); replace `Clear All` with `Close event` + protected reset.
- Attendance corrections with `AuditLog` trail; export workflow with event/date/filter/column selection, row preview, CSV output, and `ExportLog` history.

## Phase 3 — scale and polish (later)

- Browser offline queue + `POST /api/scan/batch` replay using `client_scan_id`.
- Multi-station support via `station_id` and station lists per event.
- Permission matrix for admin/event staff/scanner; account list with disabled status and last login.
- Printable QR sheets, sound/vibration, accessibility mode, attendance trends, PWA manifest/service worker.

## Verification

- Add `tests/` with pytest + TestClient smoke tests (pytest and httpx are already installed): scan duplicate/sequence, event scoping, CSV preview/confirm, permissions, audit entries.
- After each phase: run pytest, restart server, exercise the affected screens in the browser.
