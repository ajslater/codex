<template>
  <v-btn class="closeButton" icon v-bind="$attrs">
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

<style scoped lang="scss">
.closeButton .v-icon {
  margin-right: 0 !important;
}
</style>
