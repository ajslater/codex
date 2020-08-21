const BundleTracker = require("webpack-bundle-tracker");
const path = require("path");

const DEV = process.env.NODE_ENV === "development";

module.exports = {
  productionSourceMap: DEV,
  configureWebpack: {
    plugins: [new BundleTracker()],
    devServer: {
      writeToDisk: true, // Write files to disk in dev mode, so Django can serve the assets
    },
  },
  transpileDependencies: ["vuetify"],
  publicPath: "static/",
  filenameHashing: false, // Let Django do it
  outputDir: path.resolve(__dirname, "../codex/static_build"),
};
