<template>
  <v-progress-circular
    indeterminate
    :size="size"
    color="#cc7b19"
    aria-label="loading"
  />
</template>

<script>
export default {
  name: "PlaceholderLoading",
  props: {
    size: { type: Number, default: 128 },
  },
};
</script>
