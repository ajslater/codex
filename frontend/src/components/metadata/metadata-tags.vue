<template>
  <v-chip-group
    v-if="model && model.length > 0"
    v-model="model"
    multiple
    class="tags"
    :class="{ 'background-soft-highlight': true }"
  >
    <h3 class="subheader">
      {{ label }}
    </h3>
    <v-item v-for="item in model" :key="item.name">
      <v-chip small :color="chipColor(item.pk)">
        {{ item.name }}
      </v-chip>
    </v-item>
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
        ? "rgba(204, 123, 25, 0.75)"
        : "#202020";
    },
  },
};
</script>

<style scoped lang="scss">
.subheader {
  padding-left: 8px;
  padding-top: 0px;
  height: 32px;
}
.tags {
  border-radius: 3px;
  padding: 10px;
}
</style>
