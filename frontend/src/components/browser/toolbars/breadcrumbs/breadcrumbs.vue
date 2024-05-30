<template>
  <v-breadcrumbs id="browserBreadcrumbs" density="compact" :items="breadcrumbs">
    <template #item="{ item }">
      <v-breadcrumbs-item :to="item.to" :title="item.tooltip">
        <v-icon v-if="item.icon">{{ item.icon }}</v-icon>
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
        const crumbs = [];
        if (!state.page.breadcrumbs) {
          return crumbs;
        }
        let parentPks = "";
        for (const crumb of state.page.breadcrumbs) {
          const to = this.getTo(crumb, parentPks);
          const title = crumb.name ? crumb.name : "";
          const group = crumb.group;
          const icon = this.getIcon(crumb.pks, title, group);
          const tooltip = crumb.pks === "0" ? "Top" : GROUP_NAME_MAP[group];
          const displayCrumb = { to, title, icon, tooltip };
          crumbs.push(displayCrumb);
          parentPks = crumb.pks;
        }
        return crumbs;
      },
    }),
  },
  methods: {
    getTo(crumb, parentPks) {
      const params = { ...crumb };
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
#browserBreadcrumbs {
  max-width: 100vw;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
  padding-top: 0px;
  padding-bottom: 0px;
  padding-left: 8px;
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
</style>
