<template>
  <v-chip
    :color="result.ok ? 'success' : 'error'"
    :prepend-icon="result.ok ? mdiCheckCircle : mdiAlertCircle"
    size="small"
    variant="tonal"
    class="validationChip"
  >
    {{ chipText }}
  </v-chip>
</template>

<script>
import { mdiAlertCircle, mdiCheckCircle } from "@mdi/js";

import { NUMBER_FORMAT } from "@/datetime";

export default {
  name: "TaggingValidationChip",
  props: {
    result: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      mdiAlertCircle,
      mdiCheckCircle,
    };
  },
  computed: {
    rateLimitText() {
      // The account's live limits, read off the validation response's
      // X-RateLimit-* headers. Metron's daily sustained limit varies by
      // donor tier, so it's the number worth showing; VerseDB reports an
      // hourly window.
      const limits = this.result.rateLimits;
      if (!this.result.ok || !limits) return "";
      const parts = [];
      if (limits.burst?.limit != null) {
        // Burst remaining is noise for a one-shot check; show the cap.
        parts.push(`${NUMBER_FORMAT.format(limits.burst.limit)}/min`);
      }
      const hourly = limits.hourly || {};
      if (hourly.remaining != null && hourly.limit != null) {
        parts.push(
          `${NUMBER_FORMAT.format(hourly.remaining)} of ${NUMBER_FORMAT.format(hourly.limit)} left this hour`,
        );
      } else if (hourly.limit != null) {
        parts.push(`${NUMBER_FORMAT.format(hourly.limit)}/hour`);
      }
      const sustained = limits.sustained || {};
      if (sustained.remaining != null && sustained.limit != null) {
        parts.push(
          `${NUMBER_FORMAT.format(sustained.remaining)} of ${NUMBER_FORMAT.format(sustained.limit)} left today`,
        );
      } else if (sustained.limit != null) {
        parts.push(`${NUMBER_FORMAT.format(sustained.limit)}/day`);
      } else if (sustained.remaining != null) {
        parts.push(`${NUMBER_FORMAT.format(sustained.remaining)} left today`);
      }
      return parts.join(" · ");
    },
    chipText() {
      if (!this.result.ok) return this.result.error || "Failed";
      const rates = this.rateLimitText;
      return rates ? `Connected · ${rates}` : "Connected";
    },
  },
};
</script>

<style scoped lang="scss">
.validationChip {
  align-self: flex-start;
}
</style>
