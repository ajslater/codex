# 05 — Bundle splitting + startup parallelization

Smallest sub-plan. Ships last, since the runtime perf work is
where the user-visible wins live.

## Vite config: manual chunk splitting

`frontend/vite.config.js` defines a single `rollupOptions.input
= main.js`. Rollup will produce one big chunk plus its
auto-derived dynamic chunks (the `MainAdmin` / `MainBrowser` /
`MainReader` lazy routes). The vendor code (Vue, Vuetify,
Pinia, xior, etc.) lands inline in those chunks.

**Fix**: add a `manualChunks` function that pulls vendor
modules into a stable `vendor` chunk:

```js
build: {
  rollupOptions: {
    input: path.resolve("./src/main.js"),
    output: {
      manualChunks(id) {
        if (id.includes("node_modules/vue") ||
            id.includes("node_modules/@vue") ||
            id.includes("node_modules/pinia") ||
            id.includes("node_modules/vue-router")) {
          return "vendor-vue";
        }
        if (id.includes("node_modules/vuetify") ||
            id.includes("node_modules/@mdi")) {
          return "vendor-vuetify";
        }
      },
    },
  },
},
```

The split lets browsers cache vendor code across codex
releases — most updates touch app code, not vendor. Saves a
~500-1000 KB re-download per release for cached visitors.

Fine-tuning chunk boundaries:
- Vue + Pinia + Vue Router travel together (shared internals).
- Vuetify is large enough on its own that splitting it from Vue
  is right.
- `@mdi/js` icon set ships with Vuetify; co-locate.

Verify chunk sizes with `rollup-plugin-visualizer` after the
change. Adjust if a chunk is unexpectedly small (boundary not
worth the extra HTTP request) or unexpectedly large.

## Startup parallelization

`app.vue`'s `created` hook chains `loadProfile().then(setTimezone)`,
plus a watcher on `user` that also calls `setTimezone`.
Sub-plan 02 fixes the duplicate (I); the bigger startup win is
parallelizing the cold-boot fetches:

```js
// app.vue
async created() {
  const promises = [
    loadProfile(),
    loadOPDSURLs(),       // currently lazy-loaded; pre-warm
    loadAdminFlags(),     // if not already in flight
  ];
  await Promise.allSettled(promises);
  // setTimezone fires from the user watcher
}
```

`Promise.allSettled` rather than `Promise.all` so a failing
secondary fetch doesn't block the SPA from rendering. Each
endpoint is independent; series-then-parallel removes one round
trip on cold boot.

## Bundle audit pass

After the chunk split lands, run:

```sh
cd frontend && bun run build
ls -lh ../codex/static_build/static/*.js
```

Identify any single chunk > 500 KB gzipped that isn't a known
vendor. Common culprits worth checking:

- The browser route's lazy chunk if it pulls all of `metadata/`
  + `admin/` transitively. The `MainAdmin` and `MainBrowser`
  lazy routes should not share much.
- `@mdi/js` if used outside the Vuetify-managed import path.
  Drop unused icons via the `vite-plugin-vuetify`'s tree-shake.

## Correctness invariants

- **Manual chunk boundaries don't change runtime behavior**:
  modules are loaded eagerly when imported, lazily when
  `import()`'d — `manualChunks` only changes which file each
  module ships in.
- **`Promise.allSettled` doesn't surface errors**: each
  promise's failure is independent. If `loadOPDSURLs` 500s,
  the SPA still boots; the OPDS link panel just doesn't
  populate. Add per-call logging.

## Risks

- **Chunk split too granular**: more files = more HTTP
  requests on cold visit. With HTTP/2 multiplexing this is
  cheap, but a 50-chunk-output is still bad UX. Aim for ~5-7
  chunks.
- **`vite-plugin-dynamic-base` interaction**: the existing
  plugin rewrites `import.meta.url` references to honor
  `CODEX.APP_PATH`. Verify it still rewrites the new vendor
  chunks correctly.

## Suggested commit shape

One PR, two commits:

1. **`vite: manual chunks for vendor splitting`** (~30 LOC)
2. **`app: parallel cold-boot fetches via Promise.allSettled`** (~20 LOC)

## Test plan

- After the chunk split, verify the manifest produces
  `vendor-vue.<hash>.js` and `vendor-vuetify.<hash>.js`. Cold
  load a freshly-hashed app build, then deploy a no-op app
  change — verify the vendor chunks come from cache (304 / no
  request in devtools).
- Time first-paint on a cold cache before/after the
  parallelization. Should be one round-trip faster.
