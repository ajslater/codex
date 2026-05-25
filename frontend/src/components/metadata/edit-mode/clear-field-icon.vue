<template>
  <v-tooltip :text="tooltip" location="top" :open-delay="2000">
    <template #activator="{ props: tipProps }">
      <v-icon v-bind="tipProps" size="small" @click.stop="$emit('toggle')">
        {{ icon }}
      </v-icon>
    </template>
  </v-tooltip>
</template>

<script>
import { mdiDeleteOutline, mdiUndoVariant } from "@mdi/js";

export default {
  name: "ClearFieldIcon",
  props: {
    cleared: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["toggle"],
  computed: {
    icon() {
      return this.cleared ? mdiUndoVariant : mdiDeleteOutline;
    },
    tooltip() {
      return this.cleared
        ? "Undo: field will not be cleared"
        : "Clear this field on save";
    },
  },
};
</script>
