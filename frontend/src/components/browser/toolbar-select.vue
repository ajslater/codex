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
  },
};
</script>

<style lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .toolbarSelect .v-field {
    --v-field-padding-start: 4px;
    --v-field-padding-end: 0px;
  }
  .toolbarSelect .v-field--appended {
    padding-inline-end: 0px;
  }
  .toolbarSelect .v-icon {
    margin-left: 0px;
  }
}
</style>
