import { createRouter, createWebHistory } from "vue-router";

import CHOICES from "@/choices.json";
const MainAdmin = () => import("@/admin.vue");
const MainBrowser = () => import("@/browser.vue");
const HttpError = () => import("@/http-error.vue");
const MainReader = () => import("@/reader.vue");
const AdminFlagsTab = () => import("@/components/admin/flag-tab.vue");
const AdminUsersTab = () => import("@/components/admin/user-tab.vue");
const AdminGroupsTab = () => import("@/components/admin/group-tab.vue");
const AdminLibrariesTab = () => import("@/components/admin/library-tab.vue");
const AdminTasksTab = () => import("@/components/admin/task-tab.vue");
const AdminStatsTab = () => import("@/components/admin/stats-tab.vue");

const LAST_ROUTE = {
  name: "browser",
  params: window.CODEX.LAST_ROUTE || CHOICES.browser.route,
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
    path: "/:group/:pk/:page",
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
  history: createWebHistory(window.CODEX.APP_PATH),
  routes,
});
