<template>
  <span v-if="arcPosition" id="arcPosition">{{ arcPosition }}</span>
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
        if (arc && arc.index && arc.count) {
          return `${arc.index}/${arc.count}`;
        }
        return "";
      },
    }),
  },
};
</script>
<style lang="scss" scoped>
@use "vuetify/styles/settings/variables" as vuetify;
// Arc Position
#arcPosition {
  padding-top: 13px;
  padding-left: 10px;
  padding-right: 10px;
  color: rgb(var(--v-theme-textSecondary));
  text-align: center;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #arcPosition {
    padding-left: 0px;
    padding-right: 0px;
  }
}
</style>
