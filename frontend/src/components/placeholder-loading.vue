<template>
  <v-progress-circular
    indeterminate
    size="128"
    color="#cc7b19"
    class="placeholder"
  />
</template>

<script>
export default {
  name: "PlaceholderLoading",
};
</script>

<style scoped lang="scss">
.placeholder {
  margin-top: 48px;
}
</style>
