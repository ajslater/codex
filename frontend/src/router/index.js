import Vue from "vue";
import VueRouter from "vue-router";

import MainBrowser from "@/browser.vue";
import CHOICES from "@/choices.json";
import HttpError from "@/http-error.vue";
import MainReader from "@/reader.vue";

Vue.use(VueRouter);

const LAST_ROUTE = {
  name: "browser",
  params: window.CODEX.LAST_ROUTE || CHOICES.browser.route,
};

const routes = [
  {
    name: "home",
    path: "/",
    redirect: LAST_ROUTE,
    props: true,
  },
  {
    // if this isn't first it breaks deep linking into reader
    name: "reader",
    path: "/c/:pk/:page",
    component: MainReader,
    props: true,
  },
  {
    name: "browser",
    path: "/:group/:pk/:page",
    component: MainBrowser,
    props: true,
  },
  { name: "error", path: "/error/:code", component: HttpError, props: false },
  { path: "*", redirect: "/error/404" },
];

export default new VueRouter({
  base: window.CODEX.APP_PATH,
  mode: "history",
  routes,
});
