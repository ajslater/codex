<template>
  <v-toolbar id="titleToolbar" class="toolbar">
    <v-toolbar-items v-if="isCodexViewable">
      <v-btn :class="{ invisible: !showUpButton }" :to="toUpRoute" icon ripple>
        <v-icon>{{ mdiArrowUp }}</v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-toolbar-title>
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
    toUpRoute: function () {
      if (this.showUpButton) {
        return { name: "browser", params: this.upRoute };
      }
      return "";
    },
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
  },
};
</script>

<style scoped lang="scss">
#titleToolbar {
  width: 100vw;
}
.invisible {
  visibility: hidden;
}
/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
#titleToolbar .v-toolbar__title {
  margin: auto;
  padding-right: 48px;
  padding-top: 4px;
  text-align: center;
  line-height: 120%;
  text-overflow: clip;
}

#titleToolbar .v-toolbar__title #titleToolbarPrefix {
  color: gray;
  font-size: smaller;
}

#titleToolbar .v-toolbar__title #titleToolbarSuffix {
  color: gray;
  font-size: smaller;
}

@import "vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  /* eslint-disable-next-line vue-scoped-css/no-unused-selector */
  #titleToolbar .v-toolbar__title {
    font-size: 1rem;
  }
}
</style>
