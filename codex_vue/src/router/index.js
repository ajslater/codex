import Vue from "vue";
import VueRouter from "vue-router";

import Browser from "@/browser.vue";
import NotFound from "@/not-found.vue";
import Reader from "@/reader.vue";

Vue.use(VueRouter);

const routes = [
  {
    name: "home",
    path: "/",
    redirect: { name: "browser", params: { group: "p", pk: 0 } },
    props: true,
  },
  {
    name: "browser",
    path: "/browse/:group/:pk",
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
  mode: "history",
  routes,
});
