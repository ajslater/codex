import { createRouter, createWebHistory } from "vue-router";

import { breadcrumbs } from "@/choices/browser-defaults.json";
const MainAdmin = () => import("@/admin.vue");
const MainBrowser = () => import("@/browser.vue");
const HttpError = () => import("@/http-error.vue");
const MainReader = () => import("@/reader.vue");
const AdminFlagsTab = () => import("@/components/admin/tabs/flag-tab.vue");
const AdminUsersTab = () => import("@/components/admin/tabs/user-tab.vue");
const AdminGroupsTab = () => import("@/components/admin/tabs/group-tab.vue");
const AdminLibrariesTab = () =>
  import("@/components/admin/tabs/library-tab.vue");
const AdminTasksTab = () => import("@/components/admin/tabs/task-tab.vue");
const AdminStatsTab = () => import("@/components/admin/tabs/stats-tab.vue");

const LAST_ROUTE = {
  name: "browser",
  params: globalThis.CODEX.LAST_ROUTE || breadcrumbs[0],
};

const routes = [
  {
    name: "home",
    path: "/",
    redirect: LAST_ROUTE,
  },
  {
    name: "reader",
    path: "/c/:pk/:page",
    component: MainReader,
  },
  {
    name: "browser",
    path: "/:group/:pks/:page",
    component: MainBrowser,
  },
  {
    name: "admin",
    path: "/admin",
    component: MainAdmin,
    redirect: "/admin/libraries",
    children: [
      {
        name: "admin-users",
        path: "users",
        component: AdminUsersTab,
      },
      { name: "admin-groups", path: "groups", component: AdminGroupsTab },
      {
        name: "admin-libraries",
        path: "libraries",
        component: AdminLibrariesTab,
      },
      { name: "admin-flags", path: "flags", component: AdminFlagsTab },
      { name: "admin-tasks", path: "tasks", component: AdminTasksTab },
      { name: "admin-stats", path: "stats", component: AdminStatsTab },
    ],
  },
  { name: "error", path: "/error/:code", component: HttpError, props: true },
  { name: "404", path: "/:pathMatch(.*)*", redirect: "/error/404" },
];

export default new createRouter({
  history: createWebHistory(globalThis.CODEX.APP_PATH),
  routes,
});
