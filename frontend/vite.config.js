import eslintPlugin from "@nabla/vite-plugin-eslint";
import UnheadVite from "@unhead/addons/vite";
import vue from "@vitejs/plugin-vue";
import fs from "fs";
import path from "path";
import toml from "toml";
import { defineConfig } from "vite";
import { dynamicBase } from "vite-plugin-dynamic-base";
import { viteStaticCopy } from "vite-plugin-static-copy";
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
        output: {
          manualChunks: {
            // Specifying too much here can break vue's own analysis of dynamic imports.
            "admin-drawer-panel": [
              "./src/components/admin/drawer/admin-menu.vue",
              "./src/components/admin/drawer/admin-settings-button-progress.vue",
            ],
          },
        },
      },
      sourcemap: DEV,
    },
    css: {
      devSourcemap: DEV,
    },
    define: defineObj,
    plugins: [
      vue(),
      vuetify({ autoImport: true }),
      dynamicBase({
        publicPath: 'window.CODEX.APP_PATH + "static"',
      }),
      eslintPlugin,
      viteStaticCopy({
        targets: [
          {
            dest: "js/",
            src: "src/choices.json",
            transform: (content) => JSON.stringify(JSON.parse(content)),
          },
          {
            dest: "js/",
            src: "src/choices-admin.json",
            transform: (content) => JSON.stringify(JSON.parse(content)),
          },
        ],
      }),
      UnheadVite(),
    ],
    publicDir: false,
    resolve: {
      alias: {
        "@": path.resolve("./src"),
      },
    },
    server: {
      host: true,
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
