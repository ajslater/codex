const BundleTracker = require("webpack-bundle-tracker");
const fs = require("fs");
const path = require("path");
const webpack = require("webpack");

const DEV = process.env.NODE_ENV === "development";
const packageJson = fs.readFileSync("./package.json");
const PACKAGE_VERSION = JSON.parse(packageJson).version || 0;

module.exports = {
  productionSourceMap: DEV,
  configureWebpack: {
    plugins: [
      new BundleTracker(),
      new webpack.DefinePlugin({
        "process.env": {
          VUE_APP_PACKAGE_VERSION: '"' + PACKAGE_VERSION + '"',
        },
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
