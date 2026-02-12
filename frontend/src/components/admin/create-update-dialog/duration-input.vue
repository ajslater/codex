<template>
  <div class="timer">
    <div class="timerLabel">{{ label }}</div>
    <div class="timerFields">
      <v-number-input
        class="timerNumber"
        density="compact"
        filled
        round
        label="Days"
        control-variant="stacked"
        inset
        :min="0"
        :max="365"
        v-model="days"
        :disabled="disabled"
        @update:model-value="update"
      />
      <v-number-input
        class="timerNumber"
        density="compact"
        filled
        round
        label="Hours"
        control-variant="stacked"
        inset
        :min="0"
        :max="23"
        v-model="hours"
        :disabled="disabled"
        @update:model-value="update"
      />
      <v-number-input
        class="timerNumber"
        density="compact"
        filled
        round
        label="Mins"
        control-variant="stacked"
        inset
        :min="0"
        :max="59"
        v-model="minutes"
        :disabled="disabled"
        @update:model-value="update"
      />
    </div>
  </div>
</template>

<script>
import { mdiTimerRefreshOutline } from "@mdi/js";
import { VMaskInput } from "vuetify/labs/VMaskInput";

const DEFAULT_DAYS = 0;
const DEFAULT_HOURS = 1;
const DEFAULT_MINUTES = 0;

const DURATION_RE =
  // eslint-disable-next-line security/detect-unsafe-regex
  /^(?<days>[0-3]?\d?\d\s)?(?<hours>[01]?\d|2[0-3]):(?<minutes>[0-5]\d):\d{2}$/;
export default {
  name: "DurationInput",
  components: { VMaskInput },
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
    };
  },
  created() {
    const { days, hours, minutes } = this.djangoDurationToFields(
      this.modelValue,
    );
    this.days = days;
    this.hours = hours;
    this.minutes = minutes;
  },
  computed: {
    value: {
      get() {
        return this.fieldsToDjangoDuration(this.days, this.hours, this.minutes);
      },
      // set(value) {},
    },
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
      return (
        String(days).padStart(3, "0") +
        " " +
        String(hours).padStart(2, "0") +
        ":" +
        String(minutes).padStart(2, "0") +
        ":00"
      );
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
  color: rgb(var(--v-theme-textSecondary));
}

.timerFields {
  display: flex;
  flex-wrap: none;
}

.timerIcon {
  color: rgb(var(--v-theme-textSecondary));
  margin-right: 5px;
}

.timerNumber {
  max-width: 120px;
}
</style>
