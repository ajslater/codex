<template>
  <span
    v-if="active"
    class="settingsIndicatorDot"
    aria-label="has saved settings"
  />
</template>

<script>
export default {
  name: "SettingsIndicatorDot",
  props: {
    active: {
      type: Boolean,
      default: false,
    },
  },
};
</script>

<style scoped lang="scss">
.settingsIndicatorDot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 8px;
  border-radius: 50%;
  background-color: rgb(var(--v-theme-primary));
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
