<template>
  <v-btn v-bind="$attrs" :size="size" :density="density" :icon="icon" :prepend-icon="prependIcon" :text="table" />
</template>

<script>
import { mdiPencil, mdiPlus } from "@mdi/js";


export default {
  name: "AdminCreateUpdateButton",
  props: {
    update: { type: Boolean, default: false },
    table: { type: String, required: true },
    size: {
      type: String,
      default: "default",
    },
    density: {
      type: String,
      default: "default",
    },
  },
  data() {
    return {
      mdiPencil,
    };
  },
  computed: {
    icon() {
      return this.update ? mdiPencil : undefined;
    },
    prependIcon() {
      return !this.update ? mdiPlus : undefined;
    },
    text() {
      return !this.update ? table : undefined;
    }
  }
};
</script>
