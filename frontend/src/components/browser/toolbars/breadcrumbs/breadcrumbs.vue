<template>
  <v-breadcrumbs id="browserBreadcrumbs" density="compact" :items="breadcrumbs">
    <template #item="{ item }">
      <v-breadcrumbs-item v-tooltip="item.tooltip" :to="item.to">
        <v-icon v-if="item.icon">
          {{ item.icon }}
        </v-icon>
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
import deepClone from "deep-clone";
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
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
    ...mapState(useBrowserStore, ["groupNames"]),
    ...mapState(useCommonStore, ["timestamp"]),
    ...mapState(useBrowserStore, {
      breadcrumbs(state) {
        const vueCrumbs = [];
        const parentBreadcrumbs = state.settings.breadcrumbs.slice(0, -1);
        if (!parentBreadcrumbs) {
          return vueCrumbs;
        }
        let parentPks = "";
        for (const crumb of parentBreadcrumbs) {
          const to = this.getTo(crumb, parentPks);
          const text = crumb.name || "";
          const group = crumb.group;
          const icon = this.getIcon(crumb.pks, text, group);
          let tooltipText;
          if (crumb.group === "r") {
            tooltipText = "Top";
          } else {
            tooltipText = crumb.pks == 0 ? "All " : "";
            tooltipText += this.groupNames[group];
          }
          const tooltip = { text: tooltipText, openDelay: 1500 };
          const displayCrumb = { to, text, icon, tooltip };
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
      to.query = { ts: this.timestamp };
      if (parentPks) {
        to.hash = `#card-${parentPks}`;
      }
      return to;
    },
    getIcon(pks, title, group) {
      let icon;
      if ("rfa".includes(group) && pks === "0") {
        icon = mdiFormatVerticalAlignTop;
      } else if (title) {
        icon = "";
      } else {
        icon = GROUP_ICON_MAP[group];
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
