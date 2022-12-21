<template>
  <div v-if="model && model.length > 0" class="tags">
    <v-chip-group :value="model" multiple class="chipGroup">
      <div class="label">
        {{ label }}
      </div>
      <v-chip
        v-for="item in model"
        :key="`${label}/${item.value}`"
        :color="chipColor(item.value)"
        :value="item.value"
        :text="item.title"
      />
    </v-chip-group>
  </div>
</template>

<script>
import { mdiFilter } from "@mdi/js";
import { mapState } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MetadataTags",
  props: {
    label: {
      type: String,
      required: true,
    },
    items: {
      type: Array,
      default() {
        return [];
      },
    },
    values: {
      type: Array,
      default() {
        return [];
      },
    },
  },
  data() {
    return {
      mdiFilter,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      filterValues: function (state) {
        return state.settings.filters[this.label.toLowerCase()];
      },
    }),
    model() {
      return toVuetifyItems(this.values);
    },
  },
  methods: {
    chipColor: function (pk) {
      return this.filterValues && this.filterValues.includes(pk)
        ? this.$vuetify.theme.current.colors["primary-darken-1"]
        : "";
    },
  },
};
</script>

<style scoped lang="scss">
.tags {
  padding: 10px;
  background-color: rgb(var(--v-theme-surface));
}
.label {
  color: rgb(var(--v-theme-textSecondary));
  font-size: 12px;
}
.chipGroup {
  display: inline;
}
</style>
