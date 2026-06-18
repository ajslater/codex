<template>
  <div class="statusItem">
    <div class="statusItemTitle">
      <!--
        Active-only spinner. Replaces the previous double-duty
        progress bar that served both as a "task is running"
        indicator AND as progress display — the progress bar now
        only shows when active, and only goes indeterminate when
        no numeric progress can be computed.
      -->
      <v-progress-circular
        v-if="status.active"
        class="statusActiveSpinner"
        size="10"
        width="2"
        indeterminate
      />
      {{ title }}
    </div>
    <div
      v-if="subtitle || eta || showNumbers || duration"
      class="statusItemDetails"
    >
      <div v-if="subtitle" class="statusItemSubtitle">
        {{ subtitle }}
      </div>
      <div v-if="eta" class="statusItemEta">
        {{ eta }}
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
      v-if="status.active"
      :indeterminate="indeterminate"
      :model-value="progress"
      bottom
    />
  </div>
</template>

<script>
import {
  etaRemaining,
  hasNumbers,
  isIndeterminate,
  nf,
  retryRemaining,
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
    subtitle() {
      // The label plus the live "retrying in M:SS" countdown when waiting.
      const retry = retryRemaining(this.status, this.now);
      return [this.status.subtitle, retry].filter(Boolean).join(" · ");
    },
    eta() {
      return etaRemaining(this.status, this.now);
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

.statusActiveSpinner {
  margin-right: 6px;
  color: rgb(var(--v-theme-primary));
  vertical-align: middle;
}

.statusItemDetails {
  padding-left: 1rem;
  opacity: 0.75;
  font-size: small;
}
.statusItemSubtitle {
  overflow-x: auto;
}
.statusItemEta {
  overflow-x: auto;
}
.statusItemDuration {
  float: right;
}
</style>
