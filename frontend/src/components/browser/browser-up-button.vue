<template>
  <v-btn v-if="show" icon size="x-large" :title="title" :to="to">
    <v-icon>{{ icon }}</v-icon>
  </v-btn>
</template>
<script>
import { mdiArrowUp, mdiFormatVerticalAlignTop } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
const SPECIAL_GROUPS = new Set(["a", "f"]);

export default {
  name: "BrowserUpButton",
  props: {
    top: { type: Boolean, default: false },
  },
  computed: {
    ...mapGetters(useBrowserStore, ["parentModelGroup"]),
    ...mapState(useBrowserStore, {
      upRoute: (state) => state.page.routes.up,
      title(state) {
        const group = this.top
          ? state.settings.topGroup
          : this.parentModelGroup;
        const name = state.choices.static.groupNames[group] || "All";
        return `Up to ${name}`;
      },
    }),
    show() {
      return this.upRoute && "group" in this.upRoute;
    },
    icon() {
      return this.top ? mdiFormatVerticalAlignTop : mdiArrowUp;
    },
    to() {
      let params;
      if (this.top) {
        let group = this.upRoute.group;
        if (!SPECIAL_GROUPS.has(group)) {
          group = "r";
        }
        params = { group, pk: 0, page: 1 };
      } else {
        params = this.upRoute;
      }
      return { params };
    },
  },
};
</script>
