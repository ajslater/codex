<!--
  A captioned label→value table — the one look for every key/value readout in
  the admin UI (platform stats, restore counts). Object-valued entries render as
  an indented sub-group. Data/CRUD tables use AdminTable instead. DESIGN.md §5.
-->
<template>
  <div class="adminKvBlock">
    <h3 v-if="title" class="adminKvCaption">{{ title }}</h3>
    <table class="adminKvTable">
      <tbody>
        <template v-for="[key, value] of entries" :key="key">
          <template v-if="isObject(value)">
            <tr class="adminKvGroupRow">
              <td colspan="2">{{ label(key) }}</td>
            </tr>
            <tr
              v-for="[subKey, subValue] of Object.entries(value)"
              :key="subKey"
            >
              <td class="indent">{{ label(subKey) }}</td>
              <td>{{ nf(subValue) }}</td>
            </tr>
          </template>
          <tr v-else>
            <td :class="{ indent: isIndented(key) }">{{ label(key) }}</td>
            <td>{{ nf(value) }}</td>
          </tr>
        </template>
        <slot />
      </tbody>
    </table>
  </div>
</template>

<script>
import { NUMBER_FORMAT } from "@/datetime";

export default {
  name: "AdminKeyValueTable",
  props: {
    title: { type: String, default: "" },
    items: { type: Object, required: true },
  },
  computed: {
    entries() {
      return Object.entries(this.items);
    },
  },
  methods: {
    isObject(value) {
      return value !== null && typeof value === "object";
    },
    isIndented(key) {
      return typeof key === "string" && key[0] === "+";
    },
    label(key) {
      return typeof key === "string" ? key.replace(/^\+/, "") : key;
    },
    nf(value) {
      return typeof value === "number" ? NUMBER_FORMAT.format(value) : value;
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

// Stat blocks flow as a wrapping masonry of mini-tables.
.adminKvBlock {
  display: inline-block;
  vertical-align: top;
  margin: 0 d.$space-8 d.$space-6 0;
}

.adminKvCaption {
  margin: 1em 0 d.$space-2;
  text-align: center;
  font-size: d.$text-title;
}

.adminKvGroupRow td {
  padding-top: d.$space-2;
  font-weight: bold;
  color: rgb(var(--v-theme-textPrimary));
}
</style>
