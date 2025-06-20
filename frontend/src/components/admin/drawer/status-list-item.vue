<template>
  <div class="statusItem">
    <div class="statusItemTitle">
      {{ title }}
      <div v-if="status.subtitle" class="statusItemSubtitle">
        {{ status.subtitle }}
      </div>
      <div v-if="showNumbers" class="statusItemSubtitle">
        <span v-if="showComplete"> {{ nf(status.complete) }} / </span>
        {{ nf(status.total) }}
      </div>
    </div>
    <v-progress-linear
      :indeterminate="indeterminate"
      :model-value="progress"
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
  computed: {
    showComplete() {
      return Number.isInteger(this.status.complete);
    },
    showNumbers() {
      return this.showComplete || Number.isInteger(this.status.total);
    },
    indeterminate() {
      return (
        this.status.active &&
        (!this.status.total || !Number.isInteger(this.status.complete))
      );
    },
    progress() {
      if (!this.status.total || globalThis.indeterminate) {
        return 0;
      }
      return (100 * +this.status.complete) / +this.status.total;
    },
    title() {
      return STATUS_TITLES[this.status.statusType];
    },
  },
  methods: {
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
