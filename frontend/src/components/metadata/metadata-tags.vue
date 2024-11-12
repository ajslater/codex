<template>
  <div v-if="model && model.length > 0" class="tags">
    <div v-if="label" class="chipGroupLabel">
      {{ label }}
    </div>
    <v-chip-group :column="true" multiple :value="model">
      <v-chip
        v-for="item in model"
        :color="chipColor(item.value)"
        :key="`${label}/${item.value}`"
        :value="item.value"
        @click="onClick(item.value)"
      >
        <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
        <span class="chip" :class="chipClass(item.value)">
          <a v-if="item.url" :href="item.url" target="_blank"
            >{{ item.title }}<v-icon>{{ mdiOpenInNew }}</v-icon></a
          ><span v-else>{{ item.title }}</span>
        </span>
      </v-chip>
    </v-chip-group>
  </div>
</template>

<script>
import { mdiFilter, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const GROUP_SET = new Set(["p", "i", "s", "v"]);

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
    ...mapState(useMetadataStore, {
      mdGroup: (state) => state.md.group,
      mdIds: (state) => state.md.ids,
    }),
    model() {
      return toVuetifyItems(this.values);
    },
    groupMode() {
      return GROUP_SET.has(this.filter);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    chipClass(pk) {
      return { browseChip: this.filter && pk };
    },
    chipColor(pk) {
      const highlight =
        (this.groupMode &&
          this.filter === this.mdGroup &&
          this.mdIds.includes(pk)) ||
        (this.filterValues && this.filterValues.includes(pk));

      return highlight
        ? this.$vuetify.theme.current.colors["primary-darken-1"]
        : "";
    },
    onClick(itemPk) {
      if (!this.filter || !itemPk) {
        return;
      }
      let group;
      if (this.groupMode) {
        group = this.filter;
      } else {
        group = ["f", "s"].includes(this.topGroup) ? this.topGroup : "r";
      }
      const storyArcMode = group !== "a" && this.filter === "storyArcs";
      if (!storyArcMode && !this.groupMode) {
        const settings = { filters: { [this.filter]: [itemPk] } };
        this.setSettings(settings);
      }
      const pk = storyArcMode || this.groupMode ? itemPk : 0;
      const pks = [pk].join(",");
      const params = { group, pks, page: 1 };
      const route = { name: "browser", params };
      this.$router.push(route);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.tags {
  padding: 5px;
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

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .chipGroupLabel,
  .chip {
    font-size: x-small !important;
  }
}
</style>
