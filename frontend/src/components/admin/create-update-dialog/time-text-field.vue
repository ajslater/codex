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
// /^\d{0,3}?[01]\d|2[0-3](?::[0-5]\d){2}$/.test(v) ||

const FORMAT = "DDD HH:mm:SS";
// eslint-disable-next-line security/detect-unsafe-regex
const TIME_RE = /^(?:[0-3]?\d?\d\s)?(?:[01]?\d|2[0-3])(?::[0-5]\d){2}$/;
export default {
  name: "TimeTextField",
  data() {
    return {
      FORMAT,
      timeRules: [(v) => TIME_RE.test(v) || `Invalid time format ${FORMAT}`],
    };
  },
};
</script>
