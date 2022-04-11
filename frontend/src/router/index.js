import Vue from "vue";
import VueRouter from "vue-router";

import { ROOT_PATH } from "@/api/v2/base";
import MainBrowser from "@/browser.vue";
import CHOICES from "@/choices";
import NotFound from "@/not-found.vue";
import MainReader from "@/reader.vue";

Vue.use(VueRouter);

const LAST_ROUTE = {
  name: "browser",
  params: window.lastRoute || CHOICES.browser.route,
};

const routes = [
  {
    name: "home",
    path: "/",
    redirect: LAST_ROUTE,
    props: true,
  },
  { // if this isn't first it breaks deep linking into reader
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
  { name: "notfound", path: "*", component: NotFound, props: false },
];

export default new VueRouter({
  base: ROOT_PATH,
  mode: "history",
  routes,
});
