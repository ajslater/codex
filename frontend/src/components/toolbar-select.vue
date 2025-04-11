<template>
  <v-select
    v-bind="$attrs"
    :label="selectLabel"
    :aria-label="selectLabel"
    class="toolbarSelect"
    density="compact"
    full-width
    :menu-props="{ maxHeight: undefined }"
    hide-details="auto"
    :style="style"
    variant="plain"
  >
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
    <template #item="{ item, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :title="item.title"
        :value="item.value"
      />
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
  },
  computed: {
    style() {
      if (this.maxSelectLen) {
        const attr = this.$vuetify.display.xs ? "max-width" : "width";
        const len = this.maxSelectLen * 0.7 + "em";
        return `${attr}: ${len}`;
      }
      return "";
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-label.v-field-label) {
  top: 13px;
}
:deep(.v-label.v-field-label--floating) {
  opacity: var(--v-disabled-opacity) !important;
}
:deep(.v-field:hover .v-label.v-field-label--floating),
:deep(.v-field--focused .v-label.v-field-label--floating) {
  opacity: var(--v-medium-emphasis-opacity) !important;
}
:deep(.v-field__input) {
  padding-right: 0px;
}
:deep(.v-select__menu-icon) {
  margin-left: 0px !important;
}
:deep(.v-select__selection) {
  font-size: small;
}
</style>
