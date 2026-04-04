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
import {
  hasNumbers,
  isIndeterminate,
  nf,
  statusDuration,
  statusProgress,
  statusTitle,
} from "@/components/admin/status-helpers";

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
      return hasNumbers(this.status);
    },
    indeterminate() {
      return isIndeterminate(this.status);
    },
    progress() {
      return statusProgress(this.status);
    },
    title() {
      return statusTitle(this.status.statusType);
    },
    duration() {
      return statusDuration(this.status, this.now);
    },
  },
  methods: {
    nf,
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
