<template>
  <v-toolbar id="breadcrumbsToolbar" :height="24" flat class="titleToolbar">
    <Breadcrumbs />
  </v-toolbar>
</template>

<script>
import Breadcrumbs from "@/components/browser/toolbars/breadcrumbs/breadcrumbs.vue";

export default {
  name: "BrowserHeader",
  components: {
    Breadcrumbs,
  },
};
</script>

<style scoped lang="scss">
#breadcrumbsToolbar {
  padding-top: 6px;
  padding-left: 0px; // given to first breadcrumb child
  padding-right: max(calc(env(safe-area-inset-right) / 4), 10px);
}
</style>
