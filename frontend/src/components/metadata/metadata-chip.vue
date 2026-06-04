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

const COLLECTION_SET = new Set(["publishers", "imprints", "series", "volumes"]);

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
      topCollection: (state) => state.settings.topCollection,
    }),
    ...mapState(useMetadataStore, {
      mdCollection: (state) => state.md.collection,
      mdIds: (state) => state.md.ids,
    }),
    collectionMode() {
      return COLLECTION_SET.has(this.filter);
    },
    clickable() {
      return (
        this.filter &&
        this.item.value &&
        (!this.collectionMode || this.browserShow[this.filter])
      );
    },
    classes() {
      return {
        clickable: (this.clickable || this.item.url) && !this.highlight,
      };
    },
    highlight() {
      return Boolean(
        (this.collectionMode &&
          this.filter === this.mdCollection &&
          this.mdIds.includes(this.item.value)) ||
        this.filterValues?.includes(this.item.value),
      );
    },
    variant() {
      return this.highlight ? "flat" : "tonal";
    },
    color() {
      /*
       * v-chip's ``:color`` prop accepts Vuetify theme tokens
       * directly. The previous code drilled through
       * ``this.$vuetify.theme.current.colors`` per chip per
       * render to resolve the hex string, which forced the
       * theme proxy to traverse on every chip in a
       * 50-chip-per-dialog metadata view. Returning the token
       * lets Vuetify resolve it once at the chip level via
       * its theme machinery instead.
       */
      return this.highlight ? "primary-darken-1" : "";
    },
    linkCollection() {
      let linkCollection;
      if (this.collectionMode) {
        linkCollection = this.filter;
      } else {
        linkCollection = ["folders", "series"].includes(this.topCollection)
          ? this.topCollection
          : "root";
      }
      return linkCollection;
    },
    linkPks() {
      const collectionMode =
        this.collectionMode ||
        (this.linkCollection !== "arcs" && this.filter === "storyArcs");
      return collectionMode ? this.item.value.toString() : "0";
    },
    toRoute() {
      if (!this.clickable) {
        return "";
      }
      const collection = this.linkCollection;
      const pks = this.linkPks;
      const params = { collection, pks, page: 1 };
      return { name: "browser", params };
    },
    linkSettings() {
      let settings;
      if (this.linkPks === "0") {
        settings = { filters: { [this.filter]: [this.item.value] } };
      } else {
        const topCollection = this.getTopCollection(this.linkCollection);
        settings = { topCollection };
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
      "getTopCollection",
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
