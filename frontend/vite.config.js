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
  // ``--mode analyze`` opts into a one-shot bundle-size report.
  // Run via ``bun run analyze``; opens ``frontend/bundle-stats.html``
  // with the treemap of every chunk and which modules contribute to
  // it. Used by tasks/frontend-perf/05-bundle-and-startup.md when
  // tuning the manualChunks split.
  const ANALYZE = mode === "analyze";
  // https://github.com/vitejs/vite/issues/19242
  const ALLOWED_HOSTS = DEV ? [hostname().toLowerCase()] : [];
  let publicPathPrefix = "window.CODEX.APP_PATH";
  if (PROD) {
    publicPathPrefix += ".substring(1)";
  }
  const PUBLIC_PATH = `${publicPathPrefix} + "${STATIC_DIR_NAME}"`;

  return {
    base: BASE_PATH,
    build: {
      emptyOutDir: true,
      manifest: "manifest.json",
      // ``analyze`` is a production-shape build but with the
      // visualizer plugin attached. Keep minify on so the chunk
      // sizes the visualizer reports match what users actually
      // download.
      minify: PROD || ANALYZE,
      outDir: path.resolve("../codex/static_build"),
      rollupOptions: {
        // No need for index.html
        input: path.resolve("./src/main.js"),
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
      // Bundle-size visualizer. Treemap output goes next to the
      // vite config rather than into the published static_build
      // dir so it stays a dev-only artifact.
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
