<template>
  <div class="statBlock">
    <h3>{{ title }}</h3>
    <v-table class="statsTable" striped="odd">
      <tbody>
        <tr v-for="[key, value] of Object.entries(items)" :key="key">
          <td :class="tdClasses(key)">{{ tdLabel(key) }}</td>
          <td v-if="typeof value === 'object'">
            <v-table class="statsTable" striped="even">
              <tbody>
                <tr
                  v-for="[subKey, subValue] of Object.entries(value)"
                  :key="subKey"
                >
                  <td :class="tdClasses(subKey)">{{ tdLabel(subKey) }}</td>
                  <td>{{ nf(subValue) }}</td>
                </tr>
              </tbody>
            </v-table>
          </td>
          <td v-else>{{ nf(value) }}</td>
        </tr>
        <slot />
      </tbody>
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

.statsTable {
  color: rgb(var(--v-theme-textSecondary));
  background-color: inherit;
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
