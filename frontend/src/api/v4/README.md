# API v4 client

v4 lives alongside v3 (`@/api/v3/`) while migration proceeds one store at a
time. See `tasks/api-v4.md` for the design and migration plan.

## Coexistence

Both versions share the same Django session cookie, CSRF cookie, and auth-token.
A call to `/api/v4/auth/login` logs you in for `/api/v3/` as well; logging out
via either prefix clears both. There is no "switch" — modules pick the version
they want by importing from `@/api/v3/...` or `@/api/v4/...`.

## Envelope unwrap

v4 view endpoints return `{data, meta, errors}`. The xior client in `base.js`
installs a response interceptor that unwraps `.data` on success and rejects with
a structured `APIError` carrying the first error object on failure. **Callers
consume the same shape they would in v3** — `response.data` is the inner
payload, not the envelope.

`meta` (pagination cursors, mtime, searchError) is preserved on the response as
`response.meta`. Callers that need it read it explicitly; most don't.

## Base URL

Hardcoded to `/api/v4/`. The v3 path is injected via Django template
(`globalThis.CODEX.API_V3_PATH`) for historical reasons. v4 sees no benefit from
the indirection — there's only one mount point and it's fixed by the URLconf.

## Migration cadence

- Phase 2 (this commit): `auth.js`, `session.js` — used opportunistically.
- Phase 3+: each store migrates to its v4 module when the matching backend
  endpoints land. v3 stays callable in parallel until the legacy store is
  deleted.
