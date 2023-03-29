<template>
  <v-btn rounded :icon="update" v-bind="$attrs" :size="size" :density="density">
    <v-icon v-if="update">{{ mdiPencil }}</v-icon>
    <span v-else>+ {{ table }}</span>
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
