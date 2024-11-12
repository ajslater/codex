<template>
  <div v-if="model && model.length > 0" class="tags">
    <div v-if="label" class="chipGroupLabel">
      {{ label }}
    </div>
    <v-chip-group :column="true" multiple :value="model">
      <v-chip
        v-for="item in model"
        :key="`${label}/${item.value}`"
        :color="chipColor(item.value)"
        :value="item.value"
        @click="onClick(item.value)"
      >
        <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
        <a v-if="item.url" :href="item.url" target="_blank"
          >{{ item.title }}<v-icon>{{ mdiOpenInNew }}</v-icon></a
        ><span v-else :class="chipClass">{{ item.title }}</span>
      </v-chip>
    </v-chip-group>
  </div>
</template>

<script>
import { mdiFilter, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MetadataTags",
  props: {
    label: {
      type: String,
      default: "",
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
      filterValues(state) {
        const filterName = this.filter || this.label.toLowerCase();
        return state.settings.filters[filterName];
      },
      topGroup: (state) => state.settings.topGroup,
    }),
    model() {
      return toVuetifyItems(this.values);
    },
    chipClass(pk) {
      return { browseChip: this.filter && pk };
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    chipColor(pk) {
      return this.filterValues && this.filterValues.includes(pk)
        ? this.$vuetify.theme.current.colors["primary-darken-1"]
        : "";
    },
    onClick(itemPk) {
      if (!this.filter || !itemPk) {
        return;
      }
      const group = ["f", "s"].includes(this.topGroup) ? this.topGroup : "r";
      const storyArcMode = group === "s" && this.filter === "storyArcs";
      if (!storyArcMode) {
        const settings = { filters: { [this.filter]: [itemPk] } };
        this.setSettings(settings);
      }
      const pk = storyArcMode ? itemPk : 0;
      const params = { group, pk, page: 1 };
      const route = { name: "browser", params };
      this.$router.push(route);
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
.browseChip {
  color: rgb(var(--v-theme-primary));
}
.browseChip:hover {
  color: rgb(var(--v-theme-linkHover));
}
</style>
