<template>
  <v-item-group
    v-if="model && model.length > 0"
    v-model="model"
    multiple
    class="tags"
  >
    <v-subheader class="subheader">{{ label }}</v-subheader>
    <v-item v-for="item in model" :key="item.name">
      <v-chip small :color="chipColor(item.pk)">
        {{ item.name }}
      </v-chip>
    </v-item>
  </v-item-group>
</template>

<script>
import { mdiFilter } from "@mdi/js";
import { mapState } from "vuex";

import { toVuetifyItems } from "@/api/v2/list-items";

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
    ...mapState("browser", {
      filterValues: function (state) {
        return state.settings.filters[this.label.toLowerCase()];
      },
    }),
    vuetifyItems: function () {
      return toVuetifyItems(this.values, this.items);
    },
  },
  created: function () {
    // Different than combobox, returns a list of items.
    this.model = toVuetifyItems(undefined, this.values);
    console.log(this.model);
  },
  methods: {
    chipColor: function (pk) {
      return this.filterValues && this.filterValues.includes(pk)
        ? "rgba(204, 123, 25, 0.75)"
        : "#212121";
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
  background-color: #282828;
  border-radius: 3px;
  padding: 10px;
}
</style>
