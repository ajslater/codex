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

import package_json from "./package.json";

let rootPath;
try {
  // for dev & build
  const CODEX_CONF = toml.parse(fs.readFileSync("../config/codex.toml"));
  rootPath = CODEX_CONF?.server?.url_path_prefix || "";
} catch {
  rootPath = "";
}
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
