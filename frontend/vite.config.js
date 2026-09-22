import { Unhead } from "@unhead/vue/vite";
import vue from "@vitejs/plugin-vue";
import { visualizer } from "rollup-plugin-visualizer";
import checker from "vite-plugin-checker";
import fs from "fs";
import { hostname } from "os";
import path from "path";
import toml from "toml";
import { defineConfig } from "vite";
import { dynamicBase } from "vite-plugin-dynamic-base";
import { run } from "vite-plugin-run";
import vuetify from "vite-plugin-vuetify";

import package_json from "./package.json" with { type: "json" };

/*
 * Mirror Django's URL path prefix normalization from
 * ``codex/settings/config.py``: a non-empty prefix gets exactly one
 * leading slash and no trailing slash ("codex", "/codex/",
 * "//codex//" -> "/codex"). Django normalizes the raw TOML value
 * before it reaches ``root_path`` and ``STATIC_URL``; this config
 * reads the same key straight out of the file, so without the same
 * treatment ``base`` comes out as "codex/static/" (Vite warns and
 * silently repairs it) or "/codex//static/" (Vite does *not* repair
 * that, and the doubled slash is the marker
 * vite-plugin-dynamic-base looks for when it rewrites asset URLs
 * into window.CODEX.APP_PATH).
 */
const normalizeUrlPathPrefix = (prefix) => {
  const trimmed = prefix.replace(/^\/+/, "").replace(/\/+$/, "");
  return trimmed ? `/${trimmed}` : "";
};

let rawPathPrefix;
try {
  // for dev & build
  const CODEX_CONF = toml.parse(fs.readFileSync("../config/codex.toml"));
  rawPathPrefix = CODEX_CONF?.server?.url_path_prefix || "";
} catch {
  rawPathPrefix = "";
}
const rootPath = normalizeUrlPathPrefix(rawPathPrefix);
const STATIC_DIR_NAME = "static";
const BASE_PATH = `${rootPath}/${STATIC_DIR_NAME}/`;
const IS_TEST_ENV = process.env.NODE_ENV === "test";

const defineObj = {
  CODEX_PACKAGE_VERSION: JSON.stringify(package_json.version),
};
if (IS_TEST_ENV) {
  defineObj.CODEX = {
    API_V3_PATH: JSON.stringify("dummy"),
  };
}
console.info(defineObj);

/*
 * Put Vuetify's one unlayered stylesheet back in its layer.
 *
 * 128 of Vuetify 4.2.1's 129 component stylesheets open with
 * `@layer vuetify-components`; VPullToRefresh.sass is the lone
 * file missing the `@include tools.layer('components')` every
 * sibling has, so it ships unlayered.
 *
 * Unlayered CSS outranks every layered rule regardless of
 * specificity, so `.v-pull-to-refresh { overflow: hidden }` beat
 * the scoped ID rule that makes `#browsePaneRefreshContainer` the
 * browse pane's scroller, and a library taller than the viewport
 * could not be scrolled at all.
 *
 * Matching on "no @layer" rather than on the filename means the
 * next upstream omission cannot outrank the cascade either. See
 * frontend/DESIGN.md section 10.
 */
const vuetifyLayerFix = () => ({
  name: "codex:vuetify-unlayered-css",
  enforce: "pre",
  transform(code, id) {
    const file = id.split("?")[0];
    if (
      !file.includes("/node_modules/vuetify/") ||
      !file.endsWith(".css") ||
      code.includes("@layer") ||
      // Both must stay at the top of a stylesheet, so they cannot be
      // wrapped. Vuetify ships neither today; bail rather than emit
      // CSS the browser drops on the floor.
      code.includes("@import") ||
      code.includes("@charset")
    ) {
      return null;
    }
    return { code: `@layer vuetify-components {\n${code}\n}\n`, map: null };
  },
});

const config = defineConfig(({ mode }) => {
  const PROD = mode === "production";
  const DEV = mode === "development";
  /*
   * ``--mode analyze`` opts into a one-shot bundle-size report.
   * Run via ``bun run analyze``; opens ``frontend/bundle-stats.html``
   * with the treemap of every chunk and which modules contribute to
   * it. Used by tasks/frontend-perf/05-bundle-and-startup.md when
   * tuning the manualChunks split.
   */
  const ANALYZE = mode === "analyze";
  /*
   * https://github.com/vitejs/vite/issues/19242
   * Match the host django-vite renders into <script src=...>.
   * FQDNs (e.g. box.example.com) get mangled down to the mDNS form
   * (box.local) because the FQDN resolves via WAN DNS and most
   * consumer routers don't NAT-loopback that back to the LAN. The
   * raw hostname is kept too in case it's already a single label or
   * ends in .local. Loopback names included so curl / tooling that
   * hits 127.0.0.1 or localhost:9810 don't get blocked.
   */
  const rawHost = hostname().toLowerCase();
  const mDNSHost =
    rawHost.includes(".") && !rawHost.endsWith(".local")
      ? `${rawHost.split(".")[0]}.local`
      : rawHost;
  /*
   * Mirror Django's ``_vite_dev_server_host``: explicit
   * ``VITE_HOST`` override, otherwise the mDNS-mangled hostname.
   * This is the name baked into the @vite/client's ``serverHost``
   * and ``directSocketHost`` strings, so it must be resolvable
   * from *every* browser that loads the page — not just the host.
   * Without setting ``server.hmr.host`` Vite falls back to
   * ``localhost`` whenever ``server.host`` is ``true``, which makes
   * LAN browsers connect to their own loopback and get
   * ERR_CONNECTION_REFUSED for HMR + module fetches.
   */
  const HMR_HOST = process.env.VITE_HOST?.toLowerCase() || mDNSHost;
  const ALLOWED_HOSTS = DEV
    ? [
        ...new Set([
          HMR_HOST,
          rawHost,
          mDNSHost,
          "localhost",
          "127.0.0.1",
          "[::1]",
        ]),
      ]
    : [];
  /*
   * Vite 6+ defaults ``server.cors.origin`` to a regex matching
   * only loopback / ``.localhost`` hosts. When the Django dev
   * server is browsed at e.g. ``http://hooloovoo.local:9810``, the
   * browser sends ``Origin: http://hooloovoo.local:9810`` while
   * fetching ``<script src="http://hooloovoo.local:5173/...">``.
   * That origin doesn't match Vite's default regex, so the dev
   * server replies with ``Vary: Origin`` but no
   * ``Access-Control-Allow-Origin`` and the script load is blocked.
   * Mirror ``allowedHosts`` into a CORS regex that accepts any
   * port so browser-side fetches from Django (or anything else on
   * the same hostname) work.
   */
  const reEscape = (s) => s.replace(/[$()*+.?[\\\]^{|}]/g, "\\$&");
  const CORS_ORIGIN = DEV
    ? // eslint-disable-next-line security/detect-non-literal-regexp
      new RegExp(
        `^https?://(${ALLOWED_HOSTS.map(reEscape).join("|")})(?::\\d+)?$`,
      )
    : undefined;
  /*
   * vite-plugin-dynamic-base 1.4.1 dropped the leading ``/`` that 1.4.0
   * prepended inside template-element replacements. Earlier configs
   * stripped APP_PATH's leading slash with ``.substring(1)`` to avoid a
   * double ``/`` in the rendered URL — with 1.4.1 that strip leaves the
   * modulepreload URL relative (``static/...`` instead of ``/static/...``)
   * which makes deep routes like ``/admin/libraries`` fetch chunks
   * from ``/admin/static/...`` → Django catch-all → HTML, breaking
   * lazy-loaded routes.
   */
  const PUBLIC_PATH = `window.CODEX.APP_PATH + "${STATIC_DIR_NAME}"`;

  return {
    base: BASE_PATH,
    build: {
      emptyOutDir: true,
      manifest: "manifest.json",
      /*
       * ``analyze`` is a production-shape build but with the
       * visualizer plugin attached. Keep minify on so the chunk
       * sizes the visualizer reports match what users actually
       * download.
       */
      minify: PROD || ANALYZE,
      outDir: path.resolve("../codex/static_build"),
      rollupOptions: {
        // No need for index.html
        input: path.resolve("./src/main.js"),
        output: {
          manualChunks(id) {
            /*
             * Pin Vue + Pinia + Vue Router into a stable
             * ``vendor-vue`` chunk. Loaded eagerly regardless
             * (it's in the main bundle pre-split), but rarely
             * changes between codex releases — most updates
             * touch app code. Cached visitors save the Vue
             * runtime download on every release thereafter.
             *
             * Vuetify itself is intentionally left to Vite's
             * automatic chunking. A blanket
             * ``node_modules/vuetify`` rule would pull every
             * Vuetify component used anywhere into the eager
             * bundle — including admin-only ones a typical
             * visitor never loads. The auto-split keeps
             * multi-route Vuetify in a shared chunk while
             * route-specific components stay in the route's
             * lazy chunk.
             *
             * @mdi/js is left to Vite's auto-split for the
             * same reason: pre-split it lands in its own ~17 KB
             * chunk that's already stable across releases.
             */
            if (
              id.includes("/node_modules/vue/") ||
              id.includes("/node_modules/@vue/") ||
              id.includes("/node_modules/pinia/") ||
              id.includes("/node_modules/vue-router/")
            ) {
              return "vendor-vue";
            }
          },
        },
      },
      sourcemap: DEV,
    },
    css: {
      devSourcemap: DEV,
      preprocessorOptions: {
        scss: {
          api: "modern",
        },
      },
    },
    define: defineObj,
    plugins: [
      vue(),
      vuetify({ autoImport: true }),
      vuetifyLayerFix(),
      checker({
        eslint: {
          lintCommand: "eslint_d --cache .", // "./src/**/*.{js,vue}"',
          useFlatConfig: true,
        },
      }),
      dynamicBase({
        publicPath: PUBLIC_PATH,
      }),
      run([
        {
          name: "Choices to JSON",
          run: ["../bin/build-choices.sh"],
          pattern: [
            "../codex/choices.py",
            "../codex/choices_to_json.py",
            "../bin/build-choices.sh",
          ],
        },
      ]),
      Unhead(),
      /*
       * Bundle-size visualizer. Treemap output goes next to the
       * vite config rather than into the published static_build
       * dir so it stays a dev-only artifact.
       */
      ANALYZE &&
        visualizer({
          filename: path.resolve("./bundle-stats.html"),
          template: "treemap",
          gzipSize: true,
          brotliSize: true,
          open: true,
        }),
      //     ValidatePlugin(),
    ],
    publicDir: false,
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "src"),
      },
    },
    server: {
      host: true,
      allowedHosts: ALLOWED_HOSTS,
      cors: { origin: CORS_ORIGIN },
      hmr: { host: HMR_HOST },
      strictPort: true,
    },
    test: {
      environment: "happy-dom",
      // deps: { inline: ["vuetify"] },
      globals: true,
      server: { deps: { inline: ["vuetify"] } },
    },
  };
});

export default config;
