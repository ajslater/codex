<template>
  <v-list-item class="drawerItem" slim compact />
</template>
<script>
export default {
  name: "DrawerItem",
};
</script>
<style scoped lang="scss">
.drawerItem > :deep(.v-list-item__prepend > .v-list-item__spacer) {
  display: none;
}
</style>
