<template>
  <header id="codexHeadToolbarWrapper">
    <AppBanner />
    <BrowserTopToolbar class="codexHeadToolbar" />
    <BrowserSearchToolbar class="codexHeadToolbar" />
    <BrowserBreadcrumbsToolbar class="codexHeadToolbar" />
    <BrowserTitleToolbar class="codexHeadToolbar" />
  </header>
</template>

<script>
import AppBanner from "@/components/banner.vue";
import BrowserBreadcrumbsToolbar from "@/components/browser/toolbars/breadcrumbs/browser-toolbar-breadcrumbs.vue";
import BrowserTitleToolbar from "@/components/browser/toolbars/browser-toolbar-title.vue";
import BrowserSearchToolbar from "@/components/browser/toolbars/search/browser-toolbar-search.vue";
import BrowserTopToolbar from "@/components/browser/toolbars/top/browser-toolbar-top.vue";

export default {
  name: "BrowserHeader",
  components: {
    AppBanner,
    BrowserBreadcrumbsToolbar,
    BrowserSearchToolbar,
    BrowserTopToolbar,
    BrowserTitleToolbar,
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#codexHeadToolbarWrapper {
  z-index: 100;
  position: fixed;
  width: 100vw;
}

.codexHeadToolbar {
  padding-top: env(5px + safe-area-inset-top);
  padding-left: calc(10px + env(safe-area-inset-left) / 4);
  padding-right: calc(10px + env(safe-area-inset-right) / 4);
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .codexHeadToolbar {
    padding-top: env(safe-area-inset-top);
    padding-left: calc(5px + env(safe-area-inset-left) / 4);
    padding-right: calc(5px + env(safe-area-inset-right) / 4);
  }
}
</style>
