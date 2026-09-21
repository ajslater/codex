<template>
  <div class="timer">
    <div class="timerLabel">{{ label }}</div>
    <div class="timerFields">
      <v-number-input
        v-model="days"
        :rules="rules.days"
        class="timerNumber"
        density="compact"
        filled
        round
        label="Days"
        control-variant="stacked"
        inset
        :min="0"
        :max="365"
        :disabled="disabled"
        @update:model-value="update"
      />
      <v-number-input
        v-model="hours"
        :rules="rules.hours"
        class="timerNumber"
        density="compact"
        filled
        round
        label="Hours"
        control-variant="stacked"
        inset
        :min="0"
        :max="23"
        :disabled="disabled"
        @update:model-value="update"
      />
      <v-number-input
        v-model="minutes"
        :rules="rules.minutes"
        class="timerNumber"
        density="compact"
        filled
        round
        label="Mins"
        control-variant="stacked"
        inset
        :min="0"
        :max="59"
        :disabled="disabled"
        @update:model-value="update"
      />
    </div>
  </div>
</template>

<script>
import { mdiTimerRefreshOutline } from "@mdi/js";

const DEFAULT_DAYS = 0;
const DEFAULT_HOURS = 1;
const DEFAULT_MINUTES = 0;

const DURATION_RE =
  // eslint-disable-next-line security/detect-unsafe-regex
  /^(?<days>[0-3]?\d?\d\s)?(?<hours>[01]?\d|2[0-3]):(?<minutes>[0-5]\d):\d{2}$/;
/*
 * Per-part bounds, matching the ``:min``/``:max`` already on each
 * control. Vuetify's ``$required`` alias carves out ``v === 0``, so
 * zero passes. The parts sit inside the dialog's ``<v-form>``, so
 * ``form.validate()`` disables Submit -- but rules do not stop the
 * emit, which is why ``fieldsToDjangoDuration`` guards as well.
 */
const RULES = Object.freeze({
  days: Object.freeze([["$required"], ["$intRange", [0, 365]]]),
  hours: Object.freeze([["$required"], ["$intRange", [0, 23]]]),
  minutes: Object.freeze([["$required"], ["$intRange", [0, 59]]]),
});
export default {
  name: "DurationInput",
  props: {
    label: {
      type: String,
      required: true,
    },
    modelValue: {
      type: String,
      required: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["update:modelValue"],
  data() {
    return {
      mdiTimerRefreshOutline,
      days: DEFAULT_DAYS,
      hours: DEFAULT_HOURS,
      minutes: DEFAULT_MINUTES,
      rules: RULES,
    };
  },
  computed: {
    value: {
      get() {
        return this.fieldsToDjangoDuration(this.days, this.hours, this.minutes);
      },
      // set(value) {},
    },
  },
  created() {
    const { days, hours, minutes } = this.djangoDurationToFields(
      this.modelValue,
    );
    this.days = days;
    this.hours = hours;
    this.minutes = minutes;
  },
  methods: {
    update() {
      this.$emit("update:modelValue", this.value);
    },
    djangoDurationToFields(duration) {
      const match = duration.match(DURATION_RE);
      let { days, hours, minutes } = match.groups;
      days = +days || 0;
      hours = +hours || 0;
      minutes = +minutes || 0;
      return { days, hours, minutes };
    },
    fieldsToDjangoDuration(days, hours, minutes) {
      /*
       * Clearing a part sets its model to ``null``, and ``String(null)``
       * is ``"null"`` -- four characters, so ``padStart(3, "0")`` leaves
       * it alone and the emit became ``"null 01:00:00"``. The server
       * rejects that with a 400 the dialog used to render as raw JSON.
       *
       * Coerced rather than refusing to emit: the field still reads
       * empty to the user, the rule above says so, and Submit stays
       * disabled -- but whatever does get emitted is a valid duration.
       */
      return (
        String(this.partOrZero(days)).padStart(3, "0") +
        " " +
        String(this.partOrZero(hours)).padStart(2, "0") +
        ":" +
        String(this.partOrZero(minutes)).padStart(2, "0") +
        ":00"
      );
    },
    partOrZero(value) {
      const num = Number(value);
      return Number.isFinite(num) && num >= 0 ? Math.trunc(num) : 0;
    },
  },
};
</script>
<style scoped lang="scss">
.timer {
  padding-top: 10px;
  height: 100px;
}

.timerLabel {
  font-size: small;
  color: rgb(var(--v-theme-text-secondary));
}

.timerFields {
  display: flex;
  flex-wrap: none;
}

.timerNumber {
  max-width: 120px;
}
</style>
