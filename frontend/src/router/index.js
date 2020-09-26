import Vue from "vue";
import VueRouter from "vue-router";

import { ROOT_PATH } from "@/api/v1/base";
import Browser from "@/browser.vue";
import NotFound from "@/not-found.vue";
import Reader from "@/reader.vue";

Vue.use(VueRouter);

const DEFAULT_ROUTE = {
  name: "browser",
  params: { group: "r", pk: 0, page: 1 },
};

const routes = [
  {
    name: "home",
    path: "/",
    redirect: DEFAULT_ROUTE,
    props: true,
  },
  {
    name: "browser",
    path: "/browse/:group/:pk/:page",
    component: Browser,
    props: true,
  },
  {
    name: "reader",
    path: "/read/:pk/:pageNumber",
    component: Reader,
    props: true,
  },
  { path: "*", component: NotFound },
];

export default new VueRouter({
  base: ROOT_PATH,
  mode: "history",
  routes,
});
