<template>
  <v-breadcrumbs id="browserBreadcrumbs" density="compact" :items="breadcrumbs">
    <template #item="{ item }">
      <v-breadcrumbs-item :to="item.to" :title="item.tooltip">
        <v-icon v-if="item.icon">
          {{ item.icon }}
        </v-icon>
        <span v-else>{{ item.title }}</span>
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
import deepClone from "deep-clone";
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
const GROUP_NAME_MAP = {
  f: "Folder",
  a: "Story Arc",
  r: "Top",
  p: "Publisher",
  i: "Imprint",
  s: "Series",
  v: "Volume",
};
const GROUP_ICON_MAP = {
  f: mdiFolderOutline,
  r: mdiFormatVerticalAlignTop,
  p: mdiChessRook,
  i: mdiFeather,
  s: mdiBookshelf,
};

export default {
  name: "BrowserBreadcrumbs",
  computed: {
    ...mapState(useBrowserStore, {
      breadcrumbs(state) {
        const vueCrumbs = [];
        const parentBreadcrumbs = state.settings.breadcrumbs.slice(
          0,
          state.settings.breadcrumbs.length - 1,
        );
        if (!parentBreadcrumbs) {
          return vueCrumbs;
        }
        let parentPks = "";
        for (const crumb of parentBreadcrumbs) {
          const to = this.getTo(crumb, parentPks);
          const title = crumb.name ? crumb.name : "";
          const group = crumb.group;
          const icon = this.getIcon(crumb.pks, title, group);
          const tooltip = crumb.pks === "0" ? "Top" : GROUP_NAME_MAP[group];
          const displayCrumb = { to, title, icon, tooltip };
          vueCrumbs.push(displayCrumb);
          parentPks = crumb.pks;
        }
        return vueCrumbs;
      },
    }),
  },
  methods: {
    getTo(crumb, parentPks) {
      const params = deepClone(crumb);
      delete params["name"];
      const to = { name: "browser", params };
      if (parentPks) {
        to.hash = `#card-${parentPks}`;
      }
      return to;
    },
    getIcon(pks, title, group) {
      let icon;
      if ("rfa".indexOf(group) != -1 && pks === "0") {
        icon = mdiFormatVerticalAlignTop;
      } else if (!title) {
        icon = GROUP_ICON_MAP[group];
      } else {
        icon = "";
      }
      return icon;
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;

#browserBreadcrumbs {
  max-width: 100vw;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
  padding-top: 0px;
  padding-bottom: 0px;
  padding-left: max(18px, calc(env(safe-area-inset-left)/2));
  padding-right: 0px;
}

#browserBreadcrumbs :deep(.v-breadcrumbs-item) {
  padding: 0px;
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

@media #{map-get(vuetify.$display-breakpoints, 'xs')} {
  #browserBreadcrumbs {
    padding-left: max(10px, calc(env(safe-area-inset-left)/2));
  }
}
</style>
