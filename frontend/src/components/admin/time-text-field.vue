<template>
  <v-text-field
    ref="timeField"
    density="compact"
    filled
    :hint="FORMAT"
    round
    :rules="timeRules"
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "TimeTextField",
  data() {
    return {
      FORMAT: "DDD HH:mm:SS",
      timeRules: [
        (v) =>
          /^(\d{1,3} )?([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/.test(v) ||
          `Invalid time format ${this.FORMAT}`,
      ],
    };
  },
};
</script>
