<template>
  <v-btn icon v-bind="$attrs">
    <v-icon>{{ mdiClose }}</v-icon>
  </v-btn>
</template>
<script>
import { mdiClose } from "@mdi/js";
export default {
  name: "CloseButton",
  data() {
    return {
      mdiClose,
    };
  },
};
</script>
