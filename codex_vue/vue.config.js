const BundleTracker = require("webpack-bundle-tracker");

const DEV = process.env.NODE_ENV === "development";

const STATIC_DIR = "static/dist/";

module.exports = {
  outputDir: STATIC_DIR,
  productionSourceMap: DEV,
  configureWebpack: {
    plugins: [new BundleTracker()],
  },
  transpileDependencies: ["vuetify"],
  publicPath: `/${STATIC_DIR}`,
};
