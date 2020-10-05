<template>
  <v-toolbar id="titleToolbar" class="toolbar" dense>
    <v-toolbar-items>
      <v-btn :class="{ invisible: !showUpButton }" :to="upTo" icon ripple
        ><v-icon>{{ mdiArrowUp }}</v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-toolbar-title>
      {{ longBrowseTitle }}
    </v-toolbar-title>
  </v-toolbar>
</template>

<script>
import { mdiArrowUp } from "@mdi/js";
import { mapState } from "vuex";

import { getVolumeName } from "@/components/comic-name";

export default {
  name: "BrowserHeader",
  data() {
    return {
      mdiArrowUp,
    };
  },
  computed: {
    ...mapState("browser", {
      browserTitle: (state) => state.browserTitle,
      upRoute: (state) => state.routes.up,
    }),
    upTo: function () {
      if (this.showUpButton) {
        return { name: "browser", params: this.upRoute };
      }
      return "";
    },
    showUpButton: function () {
      return this.upRoute && this.upRoute.group;
    },
    longBrowseTitle: function () {
      let browserTitle;
      const group = this.$route.params.group;
      if (+this.$route.params.pk === 0) {
        browserTitle = this.browserTitle.groupName;
      } else if (group === "v") {
        const { parentName, groupName, groupCount } = this.browserTitle;
        const volumeName = getVolumeName(groupName);
        browserTitle = "";
        if (parentName) {
          browserTitle += `${parentName} `;
        }
        browserTitle += `${volumeName}`;
        if (this.browserTitle.volumeCount) {
          browserTitle += ` of ${groupCount}`;
        }
      } else {
        browserTitle = this.browserTitle.groupName;
      }
      return browserTitle;
    },
  },
};
</script>

<style scoped lang="scss">
#titleToolbar {
  width: 100vw;
}
</style>
<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
#titleToolbar .v-toolbar__title {
  margin: auto;
}
#titleToolbar .v-toolbar__content {
  padding: 0px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #titleToolbar .v-toolbar__title {
    font-size: 0.75rem;
  }
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
