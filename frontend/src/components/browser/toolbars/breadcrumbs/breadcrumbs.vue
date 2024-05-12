<template>
  <span id="crumbs">
    <span id="headCrumbs">
      <Breadcrumb v-for="item of headCrumbs" :key="item.to" :item="item" />
    </span>
    <span id="tailCrumbWrapper">
      <Breadcrumb v-if="tailCrumb" id="tailCrumb" :item="tailCrumb" />
    </span>
  </span>
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

import Breadcrumb from "@/components/browser/toolbars/breadcrumbs/crumb.vue";
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
  components: {
    Breadcrumb,
  },
  computed: {
    ...mapState(useBrowserStore, {
      breadcrumbs(state) {
        const crumbs = [];
        if (!state.page.breadcrumbs) {
          return crumbs;
        }
        let first = true;
        let divider = true;
        let parentPks = "";
        for (const crumb of state.page.breadcrumbs) {
          [divider, first] = this.getDivider(first);
          const to = this.getTo(crumb, parentPks);
          const title = crumb.name ? crumb.name : "";
          const group = crumb.group;
          const icon = this.getIcon(crumb.pks, title, group);
          const tooltip = crumb.pks === "0" ? "Top" : GROUP_NAME_MAP[group];
          const displayCrumb = { to, title, icon, tooltip, divider };
          crumbs.push(displayCrumb);
          parentPks = crumb.pks;
        }
        return crumbs;
      },
      headCrumbs() {
        let head;
        const bc = this.breadcrumbs;
        if (bc.length > 1) {
          head = bc.slice(0, -1);
        } else {
          head = bc;
        }
        return head;
      },
      tailCrumb() {
        let tail = "";
        const bc = this.breadcrumbs;
        if (bc.length > 1) {
          tail = bc[bc.length - 1];
        }
        return tail;
      },
    }),
  },
  methods: {
    getDivider(first) {
      let divider;
      if (first) {
        divider = false;
        first = false;
      } else {
        divider = true;
      }
      return [divider, first];
    },
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
      if (pks === "0") {
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
#crumbs {
  display: flex;
  max-width: 100vw;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
}
#headCrumbs {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
#tailCrumbWrapper {
  padding-top: 5px;
  white-space: nowrap;

}
#crumbs :deep(a) {
  color: rgb(var(--v-theme-textDisabled));
}
#crumbs :deep(a:hover) {
  color: white;
}
#headCrumbs :deep(.crumb:first-child .v-icon) {
  font-size: xx-large;
  padding-left: max(4px, calc(env(safe-area-inset-left)/4));
  min-width: 40px;
}
</style>
