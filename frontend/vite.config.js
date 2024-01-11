import UnheadVite from "@unhead/addons/vite";
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
    fs.readFileSync("../config/hypercorn.toml"),
  );
  rootPath = HYPERCORN_CONF.root_path || "";
} catch {
  rootPath = "";
}
const BASE_PATH = rootPath + "/static/";

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
    server: {
      host: true,
      strictPort: true,
    },
    build: {
      manifest: "manifest.json",
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
        resolvers: [Vuetify3Resolver()],
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
      UnheadVite(),
    ],
    publicDir: false,
    css: {
      devSourcemap: DEV,
    },
    define: defineObj,
    test: {
      environment: "jsdom",
      // deps: { inline: ["vuetify"] },
      globals: true,
      server: { deps: { inline: ["vuetify"] } },
    },
  };
});

export default config;
