<template>
  <v-chip
    :color="result.ok ? 'success' : 'error'"
    :prepend-icon="result.ok ? 'mdi-check-circle' : 'mdi-alert-circle'"
    size="small"
    variant="tonal"
    class="validationChip"
  >
    {{ chipText }}
  </v-chip>
</template>

<script>
import { NUMBER_FORMAT } from "@/datetime";

export default {
  name: "TaggingValidationChip",
  props: {
    result: {
      type: Object,
      required: true,
    },
  },
  computed: {
    rateLimitText() {
      // Metron-only: mokkari reads the account's live limits off the
      // validation response's X-RateLimit-* headers. The daily sustained
      // limit varies by donor tier, so it's the number worth showing.
      const limits = this.result.rateLimits;
      if (!this.result.ok || !limits) return "";
      const parts = [];
      if (limits.burst?.limit != null) {
        // Burst remaining is noise for a one-shot check; show the cap.
        parts.push(`${NUMBER_FORMAT.format(limits.burst.limit)}/min`);
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
