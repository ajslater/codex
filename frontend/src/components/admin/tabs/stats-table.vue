<template>
  <div class="statBlock">
    <h3>{{ title }}</h3>
    <v-table class="highlight-table">
      <tbody v-for="[key, value] of Object.entries(items)" :key="key">
        <tr v-if="typeof value === 'object'">
          <th colspan="2" class="subtitleRow">
            {{ key }}
          </th>
        </tr>
        <tr v-else>
          <td :class="tdClasses(key)">{{ tdLabel(key) }}</td>
          <td>{{ nf(value) }}</td>
        </tr>
        <tr
          v-for="[subkey, subvalue] of Object.entries(valueTable(value))"
          :key="subkey"
        >
          <td class="indent">{{ subkey }}</td>
          <td>{{ nf(subvalue) }}</td>
        </tr>
      </tbody>
      <slot />
    </v-table>
  </div>
</template>
<script>
import { NUMBER_FORMAT } from "@/datetime";
export default {
  name: "StatsTable",
  props: {
    title: { type: String, required: true },
    items: { type: Object, required: true },
  },
  data() {
    return {};
  },
  methods: {
    valueTable(value) {
      return value && typeof value === "object" ? value : {};
    },
    tdClasses(key) {
      return {
        indent: key[0] === "+",
      };
    },
    tdLabel(key) {
      return key.replace(/^\+/, "");
    },
    nf(val) {
      if (typeof val === "number") {
        return NUMBER_FORMAT.format(val);
      }
      return val;
    },
  },
};
</script>
<style lang="scss" scoped>
.statBlock {
  display: inline-block;
  vertical-align: top;
  margin-bottom: 20px;
  margin-right: 40px;
}

h3 {
  margin-top: 1em;
  text-align: center;
}

.highlight-table {
  color: rgb(var(--v-theme-textSecondary));
}

.highlight-table tbody:nth-child(even) {
  background-color: rgb(var(--v-theme-background)) !important;
}

tr td:nth-child(2) {
  text-align: right;
}

.subtitleRow {
  height: 28px !important;
  font-weight: bold !important;
  background-color: rgb(var(--v-theme-surface)) !important;
}

.indent {
  padding-left: 2em !important;
}
</style>
