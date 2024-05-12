<template>
  <span v-if="arcPosition" id="arcPosition" :title="title">
    {{ arcPosition }}</span
  >
</template>
<script>
import { mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";
export default {
  name: "ReaderArcPosition",
  computed: {
    ...mapState(useReaderStore, {
      arcPosition(state) {
        const arc = state.arc;
        if (arc && arc.index && arc.count && arc.count > 1) {
          return `${arc.index}/${arc.count}`;
        }
        return "";
      },
      title(state) {
        const arc = state.arc;
        return `book ${arc.index} of ${arc.count} in ${arc.name}`;
      },
    }),
  },
};
</script>
<style lang="scss" scoped>
@use "vuetify/styles/settings/variables" as vuetify;
#arcPosition {
  padding: 6px;
  margin-right: 6px;
  margin-left: 6px;
  color: rgb(var(--v-theme-textSecondary));
  text-align: center;
  border-radius: 5px;
  border: solid thin rgb(var(--v-theme-textDisabled));
}
</style>
