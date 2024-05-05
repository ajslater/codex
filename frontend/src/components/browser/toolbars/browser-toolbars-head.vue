<template>
  <header id="codexHeadToolbars">
    <BrowserTopToolbar />
    <BrowserBreadcrumbsToolbar />
    <BrowserTitleToolbar />
  </header>
</template>

<script>
import BrowserBreadcrumbsToolbar from "@/components/browser/toolbars/breadcrumbs/browser-toolbar-breadcrumbs.vue";
import BrowserTitleToolbar from "@/components/browser/toolbars/browser-toolbar-title.vue";
import BrowserTopToolbar from "@/components/browser/toolbars/top/browser-toolbar-top.vue";

export default {
  name: "BrowserHeadToolbars",
  components: {
    BrowserTopToolbar,
    BrowserTitleToolbar,
    BrowserBreadcrumbsToolbar,
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#codexHeadToolbars {
  z-index: 100;
  position: fixed;
  width: 100vw;
  padding-left: 10px;
  padding-right: 10px;
  padding-top: env(5px + safe-area-inset-top);
  padding-left: calc(10px + env(safe-area-inset-left) / 4);
  padding-right: calc(10px + env(safe-area-inset-right) / 4);
  background-color:  rgb(var(--v-theme-surface-light));
}

@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #codexHeadToolbars {
    padding-top: env(safe-area-inset-top);
    padding-left: calc(5px + env(safe-area-inset-left) / 4);
    padding-right: calc(5px + env(safe-area-inset-right) / 4);
  }
}
</style>
