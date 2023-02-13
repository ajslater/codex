import vue from "@vitejs/plugin-vue";
import fs from "fs";
import path from "path";
import toml from "toml";
import { Vuetify3Resolver } from "unplugin-vue-components/resolvers";
import Components from "unplugin-vue-components/vite";
import { defineConfig } from "vite";
import { dynamicBase } from "vite-plugin-dynamic-base";
import eslint from "vite-plugin-eslint";
import { viteStaticCopy } from "vite-plugin-static-copy";
import vuetify from "vite-plugin-vuetify";

import package_json from "./package.json";

let rootPath;
try {
  // for dev & build
  const HYPERCORN_CONF = toml.parse(
    fs.readFileSync("../config/hypercorn.toml")
  );
  rootPath = HYPERCORN_CONF.root_path || "";
} catch {
  rootPath = "";
}
const BASE_PATH = rootPath + "/static/";
const VITE_HMR_URL_PREFIXES = ["node_modules", "src", "@id", "@vite/client"];

const ADMIN_COMPONENT_DIR = "./src/components/admin";
const ADMIN_COMPONENT_FNS = fs
  .readdirSync(ADMIN_COMPONENT_DIR)
  .filter((fn) => fn !== "drawer" && fn.at(-1) !== "~")
  .map((fn) => ADMIN_COMPONENT_DIR + "/" + fn);
const ADMIN_DRAWER_COMPONENT_DIR = ADMIN_COMPONENT_DIR + "/drawer";
const ADMIN_DRAWER_COMPONENT_FNS = fs
  .readdirSync(ADMIN_DRAWER_COMPONENT_DIR)
  .filter((fn) => fn.at(-1) !== "~")
  .map((fn) => ADMIN_DRAWER_COMPONENT_DIR + "/" + fn);

const config = defineConfig(({ mode }) => {
  const PROD = mode === "production";
  const DEV = mode === "development";
  return {
    base: BASE_PATH,
    server: {
      host: true,
      strictPort: true,
      proxy: {
        "/": {
          target: "http://127.0.0.1:9810/",
          secure: false,
          bypass: function (req) {
            for (const prefix of VITE_HMR_URL_PREFIXES) {
              if (req.url.startsWith(BASE_PATH + prefix)) {
                return req.url;
              }
            }
          },
          ws: true,
        },
      },
    },
    build: {
      manifest: PROD,
      minify: PROD,
      outDir: path.resolve("../codex/static_build"),
      emptyOutDir: true,
      rollupOptions: {
        // No need for index.html
        input: path.resolve("./src/main.js"),
        output: {
          manualChunks: {
            admin: ["./src/admin.vue", ...ADMIN_COMPONENT_FNS],
            "admin-drawer-panel": ADMIN_DRAWER_COMPONENT_FNS,
          },
        },
      },
      sourcemap: DEV,
    },
    resolve: {
      alias: {
        "@": path.resolve("./src"),
      },
    },
    plugins: [
      vue(),
      vuetify(),
      dynamicBase({
        publicPath: 'window.CODEX.APP_PATH + "static"',
      }),
      eslint({
        lintOnStart: true,
        failOnError: false,
      }),
      Components({
        resolvers: [
          // Vuetify
          Vuetify3Resolver(),
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
      deps: { inline: ["vuetify"] },
    },
  };
});

export default config;
