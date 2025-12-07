<template>
  <v-chip
    :class="classes"
    :color="color"
    :value="item.value"
    :variant="variant"
    @click="onClick"
  >
    <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
    <a v-if="item.url" :href="item.url" target="_blank"
      ><v-icon v-if="main" class="mainStar">{{ mdiStar }}</v-icon
      >{{ title }}
      <v-icon v-if="main" class="mainStar">{{ mdiStar }}</v-icon>
      <v-icon>{{ mdiOpenInNew }}</v-icon></a
    ><span v-else>
      <v-icon v-if="main" class="mainStar">{{ mdiStar }}</v-icon>
      {{ title }}
      <v-icon v-if="main" class="mainStar">{{ mdiStar }}</v-icon>
    </span>
  </v-chip>
</template>

<script>
import { mdiOpenInNew, mdiStar } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const GROUP_SET = new Set(["p", "i", "s", "v"]);

export default {
  name: "MetadataTags",
  props: {
    item: {
      type: Object,
      required: true,
    },
    filter: {
      type: String,
      default: "",
    },
    main: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiStar,
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
      return {
        clickable: (this.clickable || this.item.url) && !this.highlight,
      };
    },
    highlight() {
      return Boolean(
        (this.groupMode &&
          this.filter === this.mdGroup &&
          this.mdIds.includes(this.item.value)) ||
        this.filterValues?.includes(this.item.value),
      );
    },
    variant() {
      return this.highlight ? "flat" : "tonal";
    },
    color() {
      const colors = this.$vuetify.theme.current.colors;
      return this.highlight ? colors["primary-darken-1"] : "";
    },
    linkGroup() {
      let linkGroup;
      if (this.groupMode) {
        linkGroup = this.filter;
      } else {
        linkGroup = ["f", "s"].includes(this.topGroup) ? this.topGroup : "r";
      }
      return linkGroup;
    },
    linkPks() {
      const groupMode =
        this.groupMode ||
        (this.linkGroup !== "a" && this.filter === "storyArcs");
      return groupMode ? this.item.value.toString() : "0";
    },
    toRoute() {
      if (!this.clickable) {
        return "";
      }
      const group = this.linkGroup;
      const pks = this.linkPks;
      const params = { group, pks, page: 1 };
      return { name: "browser", params };
    },
    linkSettings() {
      let settings;
      if (this.linkPks === "0") {
        settings = { filters: { [this.filter]: [this.item.value] } };
      } else {
        const topGroup = this.getTopGroup(this.linkGroup);
        settings = { topGroup };
      }
      return settings;
    },
    title() {
      if (this.filter === "identifiers") {
        return this.identifierSourceTitle(this.item.title);
      }
      return this.item.title;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "routeWithSettings",
      "getTopGroup",
      "identifierSourceTitle",
    ]),
    async onClick() {
      if (!this.clickable) {
        return;
      }
      this.routeWithSettings(this.linkSettings, this.toRoute);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.v-chip {
  margin: 4px;
}

.clickable :deep(.v-chip__content) {
  color: rgb(var(--v-theme-primary));
}

.clickable:hover :deep(.v-chip__content) {
  color: rgb(var(--v-theme-linkHover));
}

.mainStar {
  vertical-align: text-bottom;
}

@media #{map.get(vuetify.$display-breakpoints, 'xs')} {
  .v-chip {
    margin: 2px;
    font-size: x-small !important;
  }
}
</style>
