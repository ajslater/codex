<template>
  <div class="statusItem">
    <div class="statusItemTitle">
      {{ title }}
      <div v-if="status.subtitle" class="statusItemSubtitle">
        {{ status.subtitle }}
      </div>
      <div v-if="showNumbers || duration" class="statusItemSubtitle">
        <span v-if="showComplete"> {{ nf(status.complete) }} / </span>
        {{ nf(status.total) }}
        <span class="duration" v-if="duration">{{ duration }}</span>
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
import { NUMBER_FORMAT, getFormattedDuration } from "@/datetime";

export default {
  name: "AdminStatusListItem",
  props: {
    status: {
      type: Object,
      required: true,
    },
    now: {
      type: Number,
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
    activeTime() {
      return new Date(this.status.active).getTime();
    },
    duration() {
      if (!this.status.active) {
        return "";
      }
      return getFormattedDuration(this.activeTime, this.now);
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
.duration {
  float: right;
}
</style>
