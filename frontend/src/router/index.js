import VueRouter from "vue-router";

import CHOICES from "@/choices.json";
const MainAdmin = () => import("@/admin.vue");
const MainBrowser = () => import("@/browser.vue");
const HttpError = () => import("@/http-error.vue");
const MainReader = () => import("@/reader.vue");

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
  {
    name: "admin",
    path: "/admin",
    component: MainAdmin,
    props: true,
  },
  { name: "error", path: "/error/:code", component: HttpError, props: true },
  { name: "404", path: "*", redirect: "/error/404" },
];

export default new VueRouter({
  base: window.CODEX.APP_PATH,
  mode: "history",
  routes,
});
