<template>
  <v-breadcrumbs id="browserBreadcrumbs" density="compact" :items="breadcrumbs">
    <template #item="{ item }">
      <v-breadcrumbs-item v-tooltip="item.tooltip" :to="item.to">
        <v-icon v-if="item.icon">
          {{ item.icon }}
        </v-icon>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <span v-else v-html="item.text" />
      </v-breadcrumbs-item>
    </template>
  </v-breadcrumbs>
</template>
<script>
import {
  mdiBookshelf,
  mdiChessRook,
  mdiFeather,
  mdiFolderOutline,
  mdiFormatVerticalAlignTop,
} from "@mdi/js";
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

const COLLECTION_ICON_MAP = Object.freeze({
  folders: mdiFolderOutline,
  publishers: mdiChessRook,
  imprints: mdiFeather,
  series: mdiBookshelf,
});

export default {
  name: "BrowserBreadcrumbs",
  computed: {
    ...mapState(useCommonStore, ["timestamp"]),
    isBelowTop() {
      // The top view names no parents; anything with them is under it.
      return Boolean(this.$route?.params?.parentIds);
    },
    ...mapState(useBrowserStore, {
      breadcrumbs(state) {
        const vueCrumbs = [];
        // The last crumb is where we already are, so it is not a link.
        const parentBreadcrumbs = (state.settings.breadcrumbs || []).slice(
          0,
          -1,
        );
        let parentPks = "";
        for (const crumb of parentBreadcrumbs) {
          const to = this.getTo(crumb, parentPks);
          const text = crumb.name || "";
          const collection = crumb.collection;
          // The root crumb is the unique top-level one (no parent ids); it
          // resolves to the publishers collection.
          const isTop = !(crumb.parentIds?.length > 0);
          const icon = this.getIcon(isTop, text, collection);
          let tooltipText;
          if (collection === "publishers" && isTop) {
            tooltipText = "Top";
          } else {
            tooltipText = isTop ? "All " : "";
            tooltipText += Reflect.get(this.collectionNames, collection);
          }
          const tooltip = { text: tooltipText, openDelay: 1500 };
          const displayCrumb = { to, text, icon, tooltip };
          vueCrumbs.push(displayCrumb);
          parentPks = crumb.parentIds?.length ? crumb.parentIds.join(",") : "";
        }
        if (!vueCrumbs.length && this.isBelowTop) {
          /*
           * Nothing to climb, and not at the top. A trail is only as
           * good as the rows it was built from: a group whose parents
           * have gone missing produces one crumb, which is the current
           * view and so no link at all, stranding a deep view with
           * nothing but the back button. The top always exists.
           */
          vueCrumbs.push(this.topCrumb(state.settings.topCollection));
        }
        return vueCrumbs;
      },
      collectionNames: (state) => state.collectionNames,
    }),
  },
  methods: {
    topCrumb(topCollection) {
      return {
        to: {
          name: "browser",
          params: { collection: topCollection },
          query: { ts: this.timestamp },
        },
        text: "",
        icon: mdiFormatVerticalAlignTop,
        tooltip: { text: "Top", openDelay: 1500 },
      };
    },
    getTo(crumb, parentPks) {
      // Crumbs already speak the v4 {collection, parentIds} dialect.
      const parentIds = crumb.parentIds || [];
      const to = {
        name: "browser",
        params: parentIds.length
          ? { collection: crumb.collection, parentIds: parentIds.join(",") }
          : { collection: crumb.collection },
      };
      const query = { ts: this.timestamp };
      if (crumb.page && Number(crumb.page) !== 1) {
        query.page = Number(crumb.page);
      }
      to.query = query;
      if (parentPks) {
        to.hash = `#card-${parentPks}`;
      }
      return to;
    },
    getIcon(isTop, title, collection) {
      let icon;
      if (isTop) {
        icon = mdiFormatVerticalAlignTop;
      } else if (title) {
        icon = "";
      } else {
        icon = Reflect.get(COLLECTION_ICON_MAP, collection);
      }
      return icon;
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#browserBreadcrumbs {
  max-width: 100vw;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
  padding-top: 0px;
  padding-bottom: 0px;
  padding-left: max(18px, calc(env(safe-area-inset-left) / 2));
  padding-right: 0px;
}

#browserBreadcrumbs :deep(.v-breadcrumbs-item) {
  padding: 0px;
}

#browserBreadcrumbs :deep(.v-breadcrumbs-item--link) {
  color: rgb(var(--v-theme-textDisabled));
}

#browserBreadcrumbs :deep(.v-breadcrumbs-divider) {
  padding: 3px;
}

#browserBreadcrumbs :deep(.v-breadcrumbs-item:first-child .v-icon) {
  font-size: xx-large !important;
}

#browserBreadcrumbs :deep(a:hover) {
  color: white;
}

@media #{map.get(vuetify.$display-breakpoints, 'xs')} {
  #browserBreadcrumbs {
    padding-left: max(10px, calc(env(safe-area-inset-left) / 2));
  }
}
</style>
