import vue from "@vitejs/plugin-vue2";
import fs from "fs";
import path from "path";
import toml from "toml";
import { VuetifyResolver } from "unplugin-vue-components/resolvers";
import Components from "unplugin-vue-components/vite";
import { defineConfig } from "vite";
import eslint from "vite-plugin-eslint";
import { viteStaticCopy } from "vite-plugin-static-copy";

import package_json from "./package.json";

let root_path;
try {
  // for dev & build
  const HYPERCORN_CONF = toml.parse(
    fs.readFileSync("../config/hypercorn.toml")
  );
  root_path = HYPERCORN_CONF.root_path || "";
} catch {
  root_path = "";
}

const config = defineConfig(({ mode }) => {
  const PROD = mode === "production";
  const DEV = mode === "development";
  return {
    base: root_path + "/static/",
    server: {
      host: true,
      strictPort: true,
      open: true,
    },
    build: {
      manifest: PROD,
      minify: PROD,
      outDir: path.resolve("../codex/static_build"),
      rollupOptions: {
        // No need for index.html
        input: path.resolve("./src/main.js"),
      },
      sourcemap: DEV,
      //emptyOutDir: true
    },
    resolve: {
      alias: {
        "@": path.resolve("./src"),
      },
    },
    plugins: [
      vue(),
      eslint({
        lintOnStart: true,
        failOnError: false,
      }),
      Components({
        resolvers: [
          // Vuetify
          VuetifyResolver(),
        ],
      }),
      viteStaticCopy({
        targets: [
          {
            src: "src/choices.json",
            dest: "js/",
            transform: (content) => JSON.stringify(JSON.parse(content)),
          },
          {
            src: "src/choices-admin.json",
            dest: "js/",
            transform: (content) => JSON.stringify(JSON.parse(content)),
          },
        ],
      }),
    ],
    publicDir: false,
    css: {
      devSourcemap: DEV,
    },
    define: {
      CODEX_PACKAGE_VERSION: JSON.stringify(package_json.version),
      "import.meta.vitest": "undefined",
    },
    test: {
      environment: "jsdom",
    },
  };
});

export default config;
