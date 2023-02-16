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
        /* eslint-disable unicorn/no-unsafe-regex */
        /* eslint-disable security/detect-unsafe-regex */
        (v) =>
          /^(\d{1,3}\s)?([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/.test(v) ||
          "Invalid time format DDD HH:mm:SS",
        /* eslint-enable unicorn/no-unsafe-regex */
        /* eslint-enable security/detect-unsafe-regex */
      ],
    };
  },
};
</script>
