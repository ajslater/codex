import eslintPlugin from "@nabla/vite-plugin-eslint";
import UnheadVite from "@unhead/addons/vite";
import vue from "@vitejs/plugin-vue";
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
  const HYPERCORN_CONF = toml.parse(
    fs.readFileSync("../config/hypercorn.toml"),
  );
  rootPath = HYPERCORN_CONF.root_path || "";
} catch {
  rootPath = "";
}
const BASE_PATH = rootPath + "/static/";

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
  // https://github.com/vitejs/vite/issues/19242
  const ALLOWED_HOSTS = DEV ? [hostname().toLowerCase()] : [];

  return {
    base: BASE_PATH,
    build: {
      emptyOutDir: true,
      manifest: "manifest.json",
      minify: PROD,
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
      dynamicBase({
        publicPath: 'window.CODEX.APP_PATH + "static"',
      }),
      eslintPlugin,
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
      UnheadVite(),
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
      environment: "jsdom",
      // deps: { inline: ["vuetify"] },
      globals: true,
      server: { deps: { inline: ["vuetify"] } },
    },
  };
});

export default config;
