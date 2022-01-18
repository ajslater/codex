const BundleTracker = require("webpack-bundle-tracker");
const CopyPlugin = require("copy-webpack-plugin");
const path = require("path");

const DEV = process.env.NODE_ENV === "development";
process.env.VUE_APP_PACKAGE_VERSION = require("./package.json").version;

module.exports = {
  productionSourceMap: DEV,
  configureWebpack: {
    plugins: [
      new BundleTracker(),
      new CopyPlugin({
        patterns: [
          {
            from: "src/choices.json",
            to: "js/choices.json",
            transform(content) {
              // simple minify
              return JSON.stringify(JSON.parse(content));
            },
          },
        ],
      }),
    ],
    devServer: {
      writeToDisk: true, // Write files to disk in dev mode, so Django can serve the assets
    },
  },
  transpileDependencies: ["vuetify"],
  publicPath: "static/",
  filenameHashing: false, // Let Django do it
  outputDir: path.resolve(__dirname, "../codex/static_build"),
};
