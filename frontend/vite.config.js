import vue from "@vitejs/plugin-vue";
import fs from "fs";
import path from "path";
import toml from "toml";
// import { VuetifyResolver } from "unplugin-vue-components/resolvers";
// import Components from "unplugin-vue-components/vite";
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
      /*
      Components({
        resolvers: [
          // Vuetify
          VuetifyResolver(),
        ],
      }),
*/
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
