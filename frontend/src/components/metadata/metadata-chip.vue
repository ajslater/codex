<template>
  <v-chip
    :color="color"
    :key="`${filter}/${item.value}`"
    :value="item.value"
    @click="onClick"
  >
    <span class="chip" :class="classes">
      <a v-if="item.url" :href="item.url" target="_blank"
        >{{ item.title }}<v-icon>{{ mdiOpenInNew }}</v-icon></a
      ><span v-else>{{ item.title }}</span>
    </span>
  </v-chip>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import { GROUPS_REVERSED, useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const GROUP_SET = new Set(["p", "i", "s", "v"]);

export default {
  name: "MetadataTags",
  props: {
    item: {
      type: Object,
      require: true,
    },
    filter: {
      type: String,
      default: "",
    },
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      browserShow: (state) => state.settings.show,
      filterValues(state) {
        return state.settings.filters[this.filter];
      },
      topGroup: (state) => state.settings.topGroup,
    }),
    ...mapState(useMetadataStore, {
      mdGroup: (state) => state.md.group,
      mdIds: (state) => state.md.ids,
    }),
    groupMode() {
      return GROUP_SET.has(this.filter);
    },
    clickable() {
      return (
        this.filter &&
        this.item.value &&
        (!this.groupMode || this.browserShow[this.filter])
      );
    },
    classes() {
      return { browseChip: this.clickable || this.item.url };
    },
    color() {
      const highlight =
        (this.groupMode &&
          this.filter === this.mdGroup &&
          this.mdIds.includes(this.item.value)) ||
        (this.filterValues && this.filterValues.includes(this.item.value));

      return highlight
        ? this.$vuetify.theme.current.colors["primary-darken-1"]
        : "";
    },
    linkGroup() {
      return this.groupMode
        ? this.filter
        : ["f", "s"].includes(this.topGroup)
          ? this.topGroup
          : "r";
    },
    linkPks() {
      const groupMode =
        this.groupMode ||
        (this.linkGroup !== "a" && this.filter === "storyArcs");
      return groupMode ? this.item.value.toString() : "0";
    },
    toRoute() {
      if (!this.filter || !this.item.value) {
        return "";
      }
      const group = this.linkGroup;
      const pks = this.linkPks;
      const params = { group, pks, page: 1 };
      return { name: "browser", params };
    },
    linkTopGroup() {
      // TODO duplicate with metadata-text
      // Very similar to browser store logic, could possibly combine.
      let topGroup;
      const group = this.toRoute?.params.group;
      if (this.topGroup === group || ["a", "f"].includes(group)) {
        topGroup = group;
      } else {
        const groupIndex = GROUPS_REVERSED.indexOf(group); // + 1;
        // Determine browse top group
        for (const testGroup of GROUPS_REVERSED.slice(groupIndex)) {
          if (testGroup !== "r" && this.browserShow[testGroup]) {
            topGroup = testGroup;
            break;
          }
        }
      }
      return topGroup;
    },
    linkSettings() {
      let settings;
      if (this.linkPks === "0") {
        settings = { filters: { [this.filter]: [this.item.value] } };
      } else {
        const topGroup = this.linkTopGroup;
        settings = { topGroup };
      }
      return settings;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["validateAndSaveSettings"]),
    async onClick() {
      if (!this.clickable || !this.toRoute) {
        return;
      }
      this.validateAndSaveSettings(this.linkSettings);
      // NOT obeying redirect.
      this.$router.push(this.toRoute);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.browseChip {
  color: rgb(var(--v-theme-primary));
}

.browseChip:hover {
  color: rgb(var(--v-theme-linkHover));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .chip {
    font-size: x-small !important;
  }
}
</style>
