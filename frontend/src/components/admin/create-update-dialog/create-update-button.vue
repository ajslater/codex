<template>
  <v-btn
    v-if="update"
    :icon="mdiPencil"
    v-bind="$attrs"
    :size="size"
    :density="density"
  />
  <v-btn v-else v-bind="$attrs" :size="size" :density="density">
    + {{ table }}
  </v-btn>
</template>

<script>
import { mdiPencil } from "@mdi/js";

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
};
</script>
