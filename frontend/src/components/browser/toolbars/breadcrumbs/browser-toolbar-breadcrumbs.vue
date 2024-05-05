<template>
  <v-toolbar
    id="breadcrumbsToolbar"
    :height="24"
    class="titleToolbar"
    elevation="8"
  >
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
  padding-top:6px;
}
</style>
