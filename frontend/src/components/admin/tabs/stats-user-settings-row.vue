<template>
  <tr v-if="show">
    <th colspan="2" class="subtitleRow">{{ title }}</th>
  </tr>
  <tr v-for="[key, count] of Object.entries(items)" :key="key">
    <td class="indent">{{ keyTitle(key) }}</td>
    <td>{{ count }}</td>
  </tr>
</template>
<script>
import _ from "lodash";
export default {
  name: "UserSettingsRows",
  props: {
    title: {
      type: String,
      required: true,
    },
    stats: {
      type: Object,
      default: undefined,
    },
    lookup: {
      type: Object,
      default: undefined,
    },
  },
  computed: {
    show() {
      return this.stats && Object.keys(this.stats).length > 0;
    },
    items() {
      return this.show ? this.stats : {};
    },
  },
  methods: {
    keyTitle(key) {
      if (this.lookup === undefined) {
        return key;
      }
      const snakeKey = _.snakeCase(key);
      return this.lookup[snakeKey];
    },
  },
};
</script>
<style lang="scss" scoped>
.subtitleRow {
  height: 28px !important;
  font-weight: bold !important;
}

.indent {
  padding-left: 2em !important;
}
</style>
