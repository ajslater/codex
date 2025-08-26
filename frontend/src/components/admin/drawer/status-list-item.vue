<template>
  <div class="statusItem">
    <div class="statusItemTitle">
      {{ title }}
    </div>
    <div
      v-if="status.subtitle || showNumbers || duration"
      class="statusItemDetails"
    >
      <div v-if="status.subtitle" class="statusItemSubtitle">
        {{ status.subtitle }}
      </div>
      <div v-if="showNumbers || duration" class="statusItemProgress">
        <span v-if="showNumbers" class="statusItemProgressNumbers">
          <span v-if="showComplete"> {{ nf(status.complete) }} / </span>
          {{ nf(status.total) }}
        </span>
        <span v-if="duration" class="statusItemDuration">{{ duration }}</span>
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
import { getFormattedDuration, NUMBER_FORMAT } from "@/datetime";

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
  padding-left: 0px;
  padding-right: 0px;
  padding-bottom: 10px;
  color: rgb(var(--v-theme-textDisabled));
}

.statusItemDetails {
  padding-left: 1rem;
  opacity: 0.75;
  font-size: small;
}
.statusItemSubtitle {
  overflow-x: auto;
}
.statusItemDuration {
  float: right;
}
</style>
