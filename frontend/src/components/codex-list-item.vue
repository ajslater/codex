<template>
  <v-list-item class="codexListItem" slim compact />
</template>
<script>
export default {
  name: "CodexListItem",
};
</script>
<style scoped lang="scss">
.codexListItem :deep(> .v-list-item__prepend > .v-list-item__spacer) {
  display: none;
}
</style>
