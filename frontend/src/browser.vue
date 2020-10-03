<template>
  <div id="browser">
    <header id="browseHeader">
      <v-toolbar id="filterToolbar" class="toolbar" dense>
        <v-toolbar-items v-if="isOpenToSee" id="filterToolbarItems">
          <BrowserFilterSelect />
          <BrowserRootGroupSelect />
          <BrowserSortBySelect />
        </v-toolbar-items>
        <v-spacer />
        <v-toolbar-items id="controls">
          <BrowserSettingsMenu />
        </v-toolbar-items>
      </v-toolbar>
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
    </header>
    <v-main v-if="showPlaceHolder" id="browsePane">
      <div id="announce">
        <PlaceholderLoading />
      </div>
    </v-main>
    <v-main v-else-if="!isOpenToSee" id="browsePane">
      <div id="announce">
        <h1>
          You may log in or register with the top right
          <v-icon>{{ mdiDotsVertical }}</v-icon
          >menu
        </h1>
      </div>
    </v-main>
    <v-main v-else-if="itemsExist" id="browsePane">
      <BrowserCard
        v-for="item in objList"
        :key="`${item.group}${item.pk}`"
        :item="item"
      />
    </v-main>
    <v-main v-else-if="librariesExist" id="browsePane">
      <div id="announce">
        <div id="noComicsFound">No comics found for these filters</div>
      </div>
    </v-main>
    <v-main v-else id="browsePane">
      <div id="announce">
        <h1>No libraries have been added to Codex yet</h1>
        <h2 v-if="isAdmin">
          Use the top right <v-icon>{{ mdiDotsVertical }}</v-icon> menu to
          navigate to the admin panel and add a comic library
        </h2>
        <div v-else>
          <h2>
            An administrator must login to add some libraries that contain
            comics
          </h2>
          <h3>
            You may log in or register with the top right
            <v-icon>{{ mdiDotsVertical }}</v-icon
            >menu
          </h3>
        </div>
      </div>
    </v-main>
    <v-footer id="browseFooter">
      <v-pagination
        v-if="numPages > 1"
        :value="+$route.params.page"
        :length="numPages"
        circle
        @input="routeToPage($event)"
      />
      <a
        id="versionFooter"
        href="https://github.com/ajslater/codex"
        :title="versionTitle"
        :class="outdatedClass"
        >codex v{{ versions.installed }}
      </a>
    </v-footer>
    <v-snackbar
      id="scanNotify"
      :value="scanNotify"
      bottom
      right
      rounded
      width="183"
      :timeout="-1"
    >
      Scanning Libraries
      <v-progress-circular size="18" indeterminate color="#cc7b19" />
      <v-btn
        id="dismissScanNotify"
        title="dismiss notification"
        x-small
        ripple
        @click="setScanNotify(null)"
        >x</v-btn
      >
    </v-snackbar>
    <v-snackbar
      id="failedImportsNotify"
      :value="failedImportsNotify"
      bottom
      right
      rounded
      width="183"
      :timeout="-1"
    >
      Review failed imports in the
      <a :href="failedImportURL">Admin Panel</a>
      <v-btn
        id="dismissFailedImportsNotify"
        title="dismiss notification"
        x-small
        ripple
        @click="failedImportsNotify = false"
        >x</v-btn
      >
    </v-snackbar>
  </div>
</template>

<script>
import { mdiArrowUp, mdiDotsVertical } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import { ADMIN_URL } from "@/api/v1/auth";
import { FAILED_IMPORT_URL, getSocket } from "@/api/v1/browser";
import WS_MESSAGES from "@/choices/websocketMessages.json";
import BrowserCard from "@/components/browser-card";
import BrowserFilterSelect from "@/components/browser-filter-select";
import BrowserRootGroupSelect from "@/components/browser-root-group-select";
import BrowserSettingsMenu from "@/components/browser-settings-menu";
import BrowserSortBySelect from "@/components/browser-sort-by-select";
import { getVolumeName } from "@/components/comic-name";
import PlaceholderLoading from "@/components/placeholder-loading";

const SCAN_DONE_MSGS = new Set([
  WS_MESSAGES.admin.SCAN_DONE,
  WS_MESSAGES.admin.FAILED_IMPORTS,
]);

export default {
  name: "Browser",
  components: {
    BrowserCard,
    BrowserFilterSelect,
    BrowserRootGroupSelect,
    BrowserSettingsMenu,
    BrowserSortBySelect,
    PlaceholderLoading,
  },
  data() {
    return {
      mdiArrowUp,
      mdiDotsVertical,
      socket: undefined,
      adminURL: ADMIN_URL,
      failedImportsNotify: false,
      failedImportURL: FAILED_IMPORT_URL,
    };
  },
  computed: {
    ...mapState("browser", {
      browseTitle: (state) => state.browseTitle,
      currentRoute: (state) => state.routes.current,
      upRoute: (state) => state.routes.up,
      objList: (state) => state.objList,
      browseLoaded: (state) => state.browseLoaded,
      librariesExist: (state) => state.librariesExist,
      itemsExist: (state) => state.objList && state.objList.length > 0,
      versions: (state) => state.versions,
      scanNotify: (state) => state.scanNotify,
      numPages: (state) => state.numPages,
    }),
    ...mapState("auth", {
      user: (state) => state.user,
      enableNonUsers: (state) => state.enableNonUsers,
    }),
    ...mapGetters("auth", ["isAdmin", "isOpenToSee"]),
    showPlaceHolder: function () {
      return (
        this.enableNonUsers === undefined ||
        (!this.browseLoaded && this.isOpenToSee)
      );
    },
    longBrowseTitle: function () {
      let browseTitle;
      const group = this.$route.params.group;
      if (+this.$route.params.pk === 0) {
        browseTitle = this.browseTitle.groupName;
      } else if (group === "v") {
        const { parentName, groupName, groupCount } = this.browseTitle;
        const volumeName = getVolumeName(groupName);
        browseTitle = "";
        if (parentName) {
          browseTitle += `${parentName} `;
        }
        browseTitle += `${volumeName}`;
        if (this.browseTitle.volumeCount) {
          browseTitle += ` of ${groupCount}`;
        }
      } else {
        browseTitle = this.browseTitle.groupName;
      }
      return browseTitle;
    },
    outdated: function () {
      return this.versions.latest > this.versions.installed;
    },
    outdatedClass: function () {
      let cls;
      if (this.outdated) {
        cls = "outdated";
      } else {
        cls = "";
      }
      return cls;
    },
    versionTitle: function () {
      let title;
      if (this.outdated) {
        title = `v${this.versions.latest} is availble`;
      } else {
        title = "up to date";
      }
      return title;
    },
    upTo: function () {
      if (this.showUpButton) {
        return { name: "browser", params: this.upRoute };
      }
      return "";
    },
    showUpButton: function () {
      return this.upRoute && this.upRoute.group;
    },
  },
  watch: {
    $route(newRoute) {
      this.$store.dispatch("browser/routeChanged", newRoute.params);
    },
    user() {
      this.connectToServer();
      if (this.isAdmin) {
        this.setScanNotify(false);
      }
    },
  },
  created() {
    this.connectToServer();
  },
  beforeDestroy() {
    if (this.socket) {
      this.socket.close();
    }
  },
  methods: {
    connectToServer: function () {
      if (!this.isOpenToSee) {
        if (this.socket) {
          this.socket.close();
        }
        return;
      }
      this.$store.dispatch("browser/browseOpened", this.$route.params);
      this.socket = getSocket(this.isAdmin);
      this.socket.addEventListener("message", this.websocketListener);
    },
    websocketListener: function (event) {
      console.debug("websocket push:", event.data);
      if (event.data === WS_MESSAGES.user.LIBRARY_CHANGED) {
        this.$store.dispatch("browser/getBrowseObjects");
      } else if (this.isAdmin) {
        if (event.data === WS_MESSAGES.admin.SCAN_LIBRARY) {
          this.setScanNotify(true);
        } else if (SCAN_DONE_MSGS.has(event.data)) {
          this.setScanNotify(false);
          if (event.data === WS_MESSAGES.admin.FAILED_IMPORTS) {
            this.failedImportsNotify = true;
          }
        }
      }
    },
    routeToPage: function (page) {
      const route = {
        name: this.$route.name,
        params: { ...this.$route.params },
      };
      route.params.page = page;
      this.$router.push(route);
    },
    setScanNotify: function (value) {
      this.$store.dispatch("browser/scanNotify", value);
    },
  },
};
</script>

<style scoped lang="scss">
#browser {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
#browseHeader {
  position: fixed;
  z-index: 10;
}
.toolbar {
  width: 100vw;
}
#filterToolbar {
}
#filterToolbarItems {
  padding-top: 8px;
}
#titleToolbar {
}
#titleToolbar .v-toolbar__title {
  margin: auto;
}
#browsePane {
  display: flex;
  margin-top: 96px;
  margin-left: 15px;
  overflow: auto;
}
.invisible {
  visibility: hidden;
}
#noComicsFound {
  font-size: x-large;
  padding: 1em;
  color: gray;
}
#browseFooter {
  justify-content: center;
}
#versionFooter {
  width: 100vw;
  text-align: center;
  font-size: small;
  color: gray;
}
#dismissScanNotify {
  margin-left: 5px;
}
#announce {
  text-align: center;
}
.outdated {
  font-style: italic;
}
#failedImportsNotify a {
  padding-right: 0.5em;
}

@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #noComicsFound {
    font-size: large;
  }
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
#filterToolbar > .v-toolbar__content {
  padding-right: 0px;
}
#filterToolbar .filterSelect .v-input__prepend-inner {
  padding-right: 0px;
}
#filterToolbar .filterSelect .v-input__prepend-inner .v-input__icon > .v-icon {
  margin-top: 1px;
}
#filterToolbar .filterSelect .v-input__icon--prepend-inner svg {
  width: 16px;
}
.toolbarSelect {
  padding-top: 3px;
}
.toolbarSelect .v-input__slot {
  border: none;
}
.toolbarSelect .v-input__append-inner {
  padding-left: 0px !important;
}
.toolbarSelect .v-input__control > .v-input__slot:before {
  border: none;
}
/* ids aren't kept by vuetify for v-select. abuse classes */
.filterSelect {
  width: 144px;
}
.filterMenuHidden > .v-select-list > .v-list-item {
  display: none !important;
}
#scanNotify > .v-snack__wrapper {
  min-width: 183px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .toolbarSelect {
    font-size: 12px;
  }
  /* ids aren't kept by vuetify for v-select. abuse classes */
  .filterSelect {
    width: 120px;
  }
  .filterSelect .v-input__icon--prepend-inner svg {
    width: 13px;
  }
  #titleToolbar .v-toolbar__title {
    font-size: 0.75rem;
  }
}
#titleToolbar .v-toolbar__content {
  padding: 0px;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
