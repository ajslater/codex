<template>
  <v-chip-group
    v-if="model && model.length > 0"
    v-model="model"
    multiple
    class="tags"
  >
    <h3 class="label">
      {{ label }}
    </h3>
    <v-item-group>
      <v-item v-for="item in model" :key="item.name">
        <v-chip size="small" :color="chipColor(item.pk)">
          {{ item.name }}
        </v-chip>
      </v-item>
    </v-item-group>
  </v-chip-group>
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
      model: undefined,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      filterValues: function (state) {
        return state.settings.filters[this.label.toLowerCase()];
      },
    }),
  },
  created: function () {
    this.model = toVuetifyItems(this.values);
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
  padding-right: 0.5em;
}
</style>
