<template>
  <v-progress-circular
    indeterminate
    :size="size"
    :color="$vuetify.theme.current.colors.primary"
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
