<template>
  <div v-if="dttm">
    {{ formattedDate }}
    <div class="colTime">
      {{ formattedTime }}
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { DATE_FORMAT, getTimeFormat } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "DateTimeColumn",
  props: {
    dttm: {
      type: String,
      default: "",
    },
  },
  data() {
    return {
      date: new Date(this.dttm),
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    formattedDate: function () {
      return DATE_FORMAT.format(this.date);
    },
    formattedTime: function () {
      const timeFormat = getTimeFormat(this.twentyFourHourTime);
      return timeFormat.format(this.date);
    },
  },
  created() {},
};
</script>

<style scoped lang="scss">
.colTime {
  color: rgb(var(--v-theme-textDisabled)) !important;
}
</style>
