<template>
  <div v-if="model && model.length > 0" class="tags">
    <div class="chipGroupLabel">
      {{ label }}
    </div>
    <v-chip-group :column="true" multiple :value="model">
      <v-chip
        v-for="item in model"
        :key="`${label}/${item.value}`"
        :color="chipColor(item.value)"
        :value="item.value"
      >
        <a v-if="item.url" :href="item.url" target="_blank"
          >{{ item.title }}<v-icon>{{ mdiOpenInNew }}</v-icon></a
        ><span v-else>{{ item.title }}</span>
      </v-chip>
    </v-chip-group>
  </div>
</template>

<script>
import { mdiFilter, mdiOpenInNew } from "@mdi/js";
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
    values: {
      type: Array,
      default() {
        return [];
      },
    },
    filter: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      mdiFilter,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      filterValues: function (state) {
        const filterName = this.filter || this.label.toLowerCase();
        return state.settings.filters[filterName];
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
.chipGroupLabel {
  font-size: 12px;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
