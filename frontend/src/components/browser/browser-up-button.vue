<template>
  <v-btn v-if="show" icon size="x-large" :title="title" :to="to">
    <v-icon>{{ icon }}</v-icon>
  </v-btn>
</template>
<script>
import { mdiArrowUp, mdiFormatVerticalAlignTop } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
const TOP_ROUTE = { group: "r", pk: 0 };

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
      return this.top ? { params: TOP_ROUTE } : { params: this.upRoute };
    },
  },
};
</script>
