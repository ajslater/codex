<template>
  <span v-if="isNever">Never</span>
  <time v-else datetime="formattedDate">
    {{ formattedDate }}
    <time class="colTime" datetime="formattedTime">
      {{ formattedTime }}
    </time>
  </time>
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
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    date() {
      return new Date(this.dttm);
    },
    formattedDate() {
      return DATE_FORMAT.format(this.date);
    },
    formattedTime() {
      const timeFormat = getTimeFormat(this.twentyFourHourTime);
      return timeFormat.format(this.date);
    },
    isNever() {
      return !this.dttm || this.date.getUTCFullYear() < 2000;
    },
  },
};
</script>

<style scoped lang="scss">
.colTime {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
