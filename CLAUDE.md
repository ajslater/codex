# CLAUDE.md Codex

## Project Overview

Codex is a comic archive web server: Django 6 backend, Vue 3 frontend, SQLite
database, WebSocket status updates. Users browse and read comics (CBZ, CBR, PDF)
through a responsive web UI. A background librarian daemon watches the
filesystem for changes and manages metadata import, cover generation, and search
indexing.

## Commands

Commands are from @\~/.claude/python-devenv.md

### Local Commands

Non exhaustive list of commands specific to this repository

```bash
make install        # Install all dependencies (Python + Node)
make build-frontend # Vite production build
make collectstatic  # Django collectstatic
make build-only     # Build Python wheel (no frontend)
make build-choices  # Generate choices JSON from Django enums
```

## Architecture

### Backend (`/codex/`)

Django app served by Granian (ASGI). Key subsystems:

- **`models/`** — ORM models: Comic, Series, Publisher, Imprint, Library,
  Bookmark, Identifier. SQLite with WAL mode.
- **`views/`** — DRF ViewSets organized by feature: `browser/` (comic listings),
  `reader/` (page serving), `admin/` (CRUD), `opds/` (syndication).
- **`urls/`** — API at `/api/v3/`. Sub-routers: `/auth/`, `/c/` (reader),
  `/<group>/` (browser), `/admin/`.
- **`serializers/`** — DRF serializers for browser, reader, and admin responses.
- **`librarian/`** — Multiprocessing background daemon with dedicated threads:
    - `CoverThread` — Generate/cache comic covers
    - `ScribeThread` — Metadata import, FTS5 search index sync
    - `LibraryPollerThread` / `LibraryWatcherThread` — Filesystem monitoring
      (polling + inotify)
    - `CronThread` — Scheduled tasks (auto-import, cleanup)
    - `BookmarkThread` — Persist user reading positions
    - `NotifierThread` — Broadcast status via WebSockets
- **`websockets/`** — Django Channels consumers. Groups: `ALL` (everyone),
  `ADMIN` (staff). Broadcasts librarian task progress.
- **`settings/`** — Config loaded from `/config/codex.toml` (TOML). Env vars:
  `DEBUG`, `CODEX_CONFIG_DIR`, `TIMEZONE`.
- **`applications/`** — ASGI app layers (HTTP + WebSocket routing, lifespan).
- **`run.py`** — Granian server entry point.

### Frontend (`/frontend/`)

Vue 3 + Vite + Vuetify 4 SPA.

- **`src/stores/`** — Pinia stores: `browser`, `reader`, `auth`, `metadata`,
  `socket`, `admin`.
- **`src/api/v3/`** — HTTP client (xior) with automatic CSRF token injection.
- **`src/components/`** — Organized by view: `browser/`, `reader/`, `admin/`,
  `metadata/`, `settings/`.
- **`src/plugins/`** — Vue Router, Vuetify, drag-scroll.
- **Routes:** `/` (home), `/:group/:pks/:page` (browser), `/c/:pk/:page`
  (reader), `/admin` (dashboard).
- **Build output:** Vite builds to `/codex/static_build/`, then `collectstatic`
  copies to `/codex/static/`.

### Docker (`/Dockerfile`)

Multi-stage build with targets:

1. **`runtime-base`** — Slim Debian with runtime libs only
2. **`builder`** — Python 3.14 + Node 24 + build tools
3. **`codex-ci`** — Builder + full source + dev deps (used in CI for
   lint/test/build)
4. **`wheel-installer`** — Installs compiled wheel, strips binaries
5. **`final`** (default) — Minimal production image. Exposes port 9810, volumes
   `/comics` and `/config`.

### CI (`.github/workflows/ci.yml`)

Single workflow with three jobs: `test` -> `build` -> `deploy`. The `test` job
builds the `codex-ci` Docker target, runs lint/test/build inside it via
`docker exec`. The `build` job creates per-arch production images (amd64 +
arm64). The `deploy` job creates a multi-arch manifest and publishes to GHCR +
PyPI.

### Makefile Structure

`/Makefile` includes fragments from `/cfg/*.mk`. These are managed by the
sibling `cfg` boilerplate system. Key fragments: `codex.mk`, `django.mk`,
`frontend.mk`, `python.mk`, `docker.mk`, `ci.mk`.

### Key Libraries

- **Backend:** Django 6, Channels 4.2, DRF 3.16, Granian 2.7, comicbox (comic
  parsing), Pillow, django-cachalot, loguru
- **Frontend:** Vue 3.5, Vite 8, Vuetify 4, Pinia 3, xior
- **Database:** SQLite + WAL + FTS5 full-text search

## Project-Specific Conventions

- Released as both a Python wheel (PyPI) and Docker image (GHCR).
- Config file is TOML (`codex.toml`), not env vars.
- Browser API groups comics by: publisher, series, folder, arc, volume — the
  `group` URL param selects which.
- Choices/enums are shared between frontend and backend via generated JSON
  (`make build-choices`).
- The `compose.yaml` `ci` service mirrors the CI Docker build for local testing.

## Linting & Testing

Uses @\~/.claude/python-devenv.md

- **Python:** pytest with Django test runner. Results in `test-results/pytest/`.
- **Frontend:** vitest. Results in `test-results/`.
- **Lint:** Ruff (Python), ESLint + Prettier (JS/Vue), shellcheck, hadolint
  (Dockerfile).
