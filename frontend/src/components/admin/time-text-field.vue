<template>
  <v-text-field
    ref="timeField"
    density="compact"
    round
    filled
    :rules="timeRules"
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "TimeTextField",
  data() {
    return {
      timeRules: [
        (v) =>
          /^([01]?\d|2[0-4]):([0-5]\d)(:[0-5]\d)?:([0-5]\d)(:[0-5]\d)?$/.test(
            v
          ) || "Invalid time format d:HH:mm:SS",
      ],
    };
  },
};
</script>
