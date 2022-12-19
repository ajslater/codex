<template>
  <v-select
    v-bind="$attrs"
    :label="selectLabel"
    :aria-label="selectLabel"
    class="toolbarSelect"
    density="compact"
    full-width
    hide-details="auto"
    variant="solo"
    :style="style"
  >
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </v-select>
</template>

<script>
export default {
  name: "ToolbarSelect",
  props: {
    selectLabel: {
      type: String,
      default: "",
    },
    maxSelectLen: {
      type: Number,
      default: 0,
    },
    mobileLenAdj: {
      type: Number,
      default: 0,
    },
  },
  computed: {
    style() {
      const adj = this.$vuetify.display.smAndDown ? this.mobileLenAdj : 0;
      const val = this.maxSelectLen + adj;
      const len = val + "em";
      return `width: ${len}; min-width: ${len}; max-width: ${len}`;
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  :deep(.v-field) {
    --v-field-padding-start: 4px;
    --v-field-padding-end: 0px;
  }
  :deep(.v-field--appended) {
    padding-inline-end: 0px;
  }
  :deep(.v-icon) {
    margin-left: 0px;
  }
}
</style>
