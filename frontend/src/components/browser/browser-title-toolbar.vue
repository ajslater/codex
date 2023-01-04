<template>
  <v-toolbar id="titleToolbar" elevation="8">
    <v-toolbar-items v-if="isCodexViewable">
      <v-btn
        id="upButton"
        icon
        size="x-large"
        :class="{ invisible: !showUpButton }"
        :disabled="!showUpButton"
        :title="upTitle"
        :to="{ params: upRoute }"
      >
        <v-icon>{{ mdiArrowUp }}</v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-toolbar-title class="codexToolbarTitle">
      <span v-if="longBrowserTitlePrefix" id="titleToolbarPrefix">
        {{ longBrowserTitlePrefix }}
        <br />
      </span>
      <span id="titleToolbarMain">
        {{ longBrowseTitleMain }}
      </span>
      <span v-if="longBrowseTitleSuffix" id="titleToolbarSuffix">
        <br />
        {{ longBrowseTitleSuffix }}
      </span>
    </v-toolbar-title>
  </v-toolbar>
</template>

<script>
import { mdiArrowUp } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import { formattedVolumeName } from "@/comic-name";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserHeader",
  data() {
    return {
      mdiArrowUp,
    };
  },
  head() {
    const names = [
      "browse comics",
      this.longBrowserTitlePrefix,
      this.longBrowseTitleMain,
      this.longBrowseTitleSuffix,
    ];
    const content = names.filter(Boolean).join(" ");
    return { meta: [{ hid: "description", name: "description", content }] };
  },
  computed: {
    ...mapState(useBrowserStore, {
      groupNames: (state) => state.choices.static.groupNames,
      browserTitle: (state) => state.page.browserTitle,
      modelGroup: (state) => state.page.modelGroup,
      upRoute: (state) => state.page.routes.up,
    }),
    ...mapGetters(useAuthStore, ["isCodexViewable", "isUserAdmin"]),
    showUpButton: function () {
      return this.upRoute && "group" in this.upRoute;
    },
    longBrowserTitlePrefix: function () {
      if (this.$route.params.group === "f") {
        return this.browserTitle.parentName;
      }
      return "";
    },
    longBrowseTitleMain: function () {
      let browserTitle;
      if (Number(this.$route.params.pk) === 0) {
        browserTitle = "All";
      } else {
        let names = [];
        const { parentName, groupName, groupCount } = this.browserTitle;
        if (parentName) {
          names.push(parentName);
        }
        const group = this.$route.params.group;
        const formattedGroupName =
          group === "v" ? formattedVolumeName(groupName) : groupName;
        if (formattedGroupName) {
          names.push(formattedGroupName);
        }
        if (groupCount) {
          const formattedGroupCount = `of ${groupCount}`;
          names.push(formattedGroupCount);
        }
        const delimiter = group === "f" ? "/" : " ";
        browserTitle = names.join(delimiter);
      }
      return browserTitle;
    },
    longBrowseTitleSuffix: function () {
      const group = this.$route.params.group;
      if (group === "f") {
        return "";
      }
      return this.groupNames[this.modelGroup];
    },
    upTitle() {
      const group = this.$route.params.group || "";
      const name = this.groupNames[group] || "All";
      return `Up to ${name}`;
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#titleToolbar {
  width: 100vw;
  padding-left: 10px;
  padding-right: 10px;
}
$upButtonWidth: 64px;
:deep(#upButton.v-btn) {
  width: $upButtonWidth;
}
.invisible {
  visibility: hidden;
}
:deep(.codexToolbarTitle) {
  margin: auto;
  padding-right: $upButtonWidth;
  padding-top: 4px;
  text-align: center;
  line-height: 120%;
  text-overflow: clip;
}

#titleToolbarPrefix,
#titleToolbarSuffix {
  color: rgb(var(--v-theme-textDisabled));
  font-size: smaller;
}

@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #titleToolbar {
    padding-left: 5px;
    padding-right: 5px;
  }
  :deep(.codexToolbarTitle) {
    font-size: 1rem;
  }
}
</style>
