<template>
  <v-progress-circular
    aria-label="loading"
    class="codexProgressCircular"
    :indeterminate="indeterminate"
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "PlaceholderLoading",
  props: {
    indeterminate: {
      type: Boolean,
      default: true,
    },
  },
};
</script>

<style scoped lang="scss">
.codexProgressCircular {
  height: 50%;
  width: 50%;
}
</style>
