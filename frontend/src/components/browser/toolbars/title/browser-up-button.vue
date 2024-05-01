<template>
  <v-btn
    v-if="show"
    :key="upRoute"
    icon
    size="x-large"
    :title="title"
    :to="to"
    variant="plain"
  >
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
    ...mapGetters(useBrowserStore, ["parentModelGroup", "upRoute"]),
    ...mapState(useBrowserStore, {
      topGroup: (state) => state.settings.topGroup,
      groupNames: (state) => state.choices.static.groupNames,
    }),
    title() {
      if (!this.upRoute) {
        return "";
      }
      let text = "Up to ";
      const nameGroup =
        this.top || this.upRoute.group === "r"
          ? this.topGroup
          : this.upRoute.group;
      let groupName = this.groupNames[nameGroup] || "";
      if (!this.top && this.upRoute.name && this.upRoute.pks != "0") {
        if (groupName && groupName !== "Series") {
          groupName = groupName.slice(0, -1);
        }
        text += groupName + " " + this.upRoute.name;
      } else {
        text += "All " + groupName;
      }
      return text;
    },
    show() {
      return this.upRoute && "group" in this.upRoute;
    },
    icon() {
      return this.top ? mdiFormatVerticalAlignTop : mdiArrowUp;
    },
    to() {
      let params;
      if (this.top) {
        let group = this.upRoute?.group;
        if (!SPECIAL_GROUPS.has(group)) {
          group = "r";
        }
        params = { group, pks: "0", page: 1 };
      } else {
        params = this.upRoute;
      }
      return { params };
    },
  },
};
</script>
