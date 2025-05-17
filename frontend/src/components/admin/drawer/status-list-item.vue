<template>
  <div nav class="statusItem">
    <div class="statusItemTitle">
      {{ title(status) }}
      <div v-if="status.subtitle" class="statusItemSubtitle">
        {{ status.subtitle }}
      </div>
      <div
        v-if="showComplete(status) || Number.isInteger(status.total)"
        class="statusItemSubtitle"
      >
        <span v-if="showComplete(status)"> {{ nf(status.complete) }} / </span>
        {{ nf(status.total) }}
      </div>
    </div>
    <v-progress-linear
      :indeterminate="indeterminate(status)"
      :model-value="progress(status)"
      bottom
    />
  </div>
</template>

<script>
import STATUS_TITLES from "@/choices/admin-status-titles.json";
import { NUMBER_FORMAT } from "@/datetime";

export default {
  name: "AdminStatusListItem",
  props: {
    status: {
      type: Object,
      required: true,
    },
  },
  methods: {
    showComplete: (status) => Number.isInteger(status.complete),
    indeterminate: (status) =>
      status.active && (!status.total || !Number.isInteger(status.complete)),
    progress(status) {
      if (!status.total || globalThis.indeterminate) {
        return 0;
      }
      return (100 * +status.complete) / +status.total;
    },
    title(status) {
      return STATUS_TITLES[status.statusType];
    },
    nf(val) {
      return Number.isInteger(val) ? NUMBER_FORMAT.format(val) : "?";
    },
  },
};
</script>

<style scoped lang="scss">
.statusItem {
  padding-left: 16px;
  padding-right: 5px;
  padding-bottom: 10px;
  color: rgb(var(--v-theme-textDisabled));
}

.statusItemSubtitle {
  padding-left: 1rem;
  opacity: 0.75;
  font-size: small;
  overflow-x: auto;
}
</style>
