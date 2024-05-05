<template>
  <span class="crumb">
    <span v-if="item.divider"> / </span>
    <router-link :title="item.tooltip" :to="item.to" class="link">
      <v-icon v-if="item.icon">
        {{ item.icon }}
      </v-icon>
      <span>
        {{ item.title }}
      </span>
    </router-link>
  </span>
</template>

<script>
export default {
  name: "BrowserBreadcrumb",
  props: {
    item: { type: Object, required: true },
  },
};
</script>

<style scoped lang="scss">
.link {
/*  display: inline-block; */
}
.crumb {
  display: inline-flex;
}
</style>
