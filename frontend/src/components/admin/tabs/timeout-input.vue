<template>
  <div class="timer">
    <div class="timerLabel">{{ label }}</div>
    <div class="timerFields">
      <v-number-input
        v-model="hours"
        class="timerNumber"
        density="compact"
        filled
        round
        label="Hours"
        control-variant="stacked"
        inset
        :min="0"
        :max="99"
        :disabled="disabled"
        @update:model-value="update"
      />
      <v-number-input
        v-model="minutes"
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
      <v-number-input
        v-model="seconds"
        class="timerNumber"
        density="compact"
        filled
        round
        label="Secs"
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
export default {
  name: "TimeoutInput",
  props: {
    label: {
      type: String,
      required: true,
    },
    modelValue: {
      type: Number,
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
      hours: 0,
      minutes: 0,
      seconds: 0,
    };
  },
  created() {
    this.fromTotalSeconds(this.modelValue);
  },
  methods: {
    fromTotalSeconds(total) {
      this.hours = Math.floor(total / 3600);
      this.minutes = Math.floor((total % 3600) / 60);
      this.seconds = total % 60;
    },
    update() {
      this.$emit(
        "update:modelValue",
        this.hours * 3600 + this.minutes * 60 + this.seconds,
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

.timerNumber {
  max-width: 120px;
}
</style>
