<template>
  <div id="browser">
    <header id="browseHeader">
      <v-toolbar id="filterToolbar" class="toolbar" dense>
        <v-toolbar-items id="filterToolbarItems">
          <v-select
            ref="filterSelect"
            v-model="bookmarkFilter"
            :items="formChoices.bookmark"
            class="toolbarSelect filterSelect"
            dense
            hide-details="auto"
            ripple
            :menu-props="{
              maxHeight: '90vh',
              overflowY: false,
              contentClass: filterMenuClass,
            }"
            :prepend-inner-icon="filterInnerIcon"
            @clickHIDE:clear="clearFilters"
            @click:prepend-inner="clearFilters"
          >
            <template #selection="{ item }">
              {{ item.text }}
              <span v-if="isOtherFiltersSelected" id="filterSuffix"> + </span>
            </template>
            <template #item="data">
              <v-slide-x-transition hide-on-leave>
                <v-list-item-content>
                  <v-list-item-title>
                    {{ data.item.text }}
                  </v-list-item-title>
                </v-list-item-content>
              </v-slide-x-transition>
            </template>
            <template #append-item>
              <v-slide-x-transition hide-on-leave>
                <v-divider v-if="filterMode === 'base'" />
              </v-slide-x-transition>
              <FilterSubMenu
                v-for="filterName of filterNames"
                :key="filterName"
                :name="filterName"
                @sub-menu-click="closeFilterSelect"
              />
            </template>
          </v-select>
          <v-select
            v-model="rootGroup"
            :items="rootGroupChoices"
            class="toolbarSelect rootGroupSelect"
            dense
            hide-details="auto"
            ripple
          />
          <v-select
            v-model="sortBy"
            class="toolbarSelect sortBySelect"
            :items="formChoices.sort"
            prefix="By "
            dense
            hide-details="auto"
            ripple
          >
            <template #item="data">
              <v-list-item v-bind="data.attrs" v-on="data.on">
                <v-list-item-content>
                  <v-list-item-title>
                    {{ data.item.text }}
                    <v-icon
                      v-show="sortBy === data.item.value"
                      class="sortArrow"
                      :class="{ upsideDown: !settings.sortReverse }"
                    >
                      {{ mdiArrowUp }}
                    </v-icon>
                  </v-list-item-title>
                </v-list-item-content>
              </v-list-item>
            </template>
          </v-select>
        </v-toolbar-items>
        <v-spacer />
        <v-toolbar-items id="controls">
          <v-menu offset-y>
            <template #activator="{ on }">
              <v-btn icon ripple title="Settings" v-on="on">
                <v-icon>{{ mdiDotsVertical }}</v-icon>
              </v-btn>
            </template>
            <v-list-item-group id="settingsMenu" ripple>
              <v-dialog
                origin="center-top"
                transition="slide-y-transition"
                max-width="20em"
                overlay-opacity="0.5"
              >
                <template #activator="{ on }">
                  <v-list-item v-on="on">
                    <v-list-item-content>
                      <v-list-item-title> Settings </v-list-item-title>
                    </v-list-item-content>
                  </v-list-item>
                </template>
                <h3>Browser Settings</h3>
                <div id="settingsGroupCaption" class="text-caption">
                  Show these groups when navigating the browse heirarchy.
                </div>
                <v-checkbox
                  v-for="choice of formChoices.settingsGroup"
                  :key="choice.value"
                  :input-value="getShow(choice.value)"
                  :label="`Show ${choice.text}`"
                  dense
                  @change="setShow(choice.value, $event)"
                />
              </v-dialog>
              <AuthDialog />
              <v-list-item @click="reload">
                <v-list-item-content>
                  <v-list-item-title> Reload Libraries</v-list-item-title>
                </v-list-item-content>
              </v-list-item>
            </v-list-item-group>
          </v-menu>
        </v-toolbar-items>
      </v-toolbar>
      <v-toolbar id="titleToolbar" class="toolbar" dense>
        <v-toolbar-items>
          <v-btn :class="{ invisible: !showUpButton }" :to="upTo" icon ripple
            ><v-icon>{{ mdiArrowUp }}</v-icon>
          </v-btn>
        </v-toolbar-items>
        <v-toolbar-title>
          {{ browseTitle }}
        </v-toolbar-title>
      </v-toolbar>
    </header>
    <v-main v-if="!browseLoaded" id="browsePane">
      <PlaceholderLoading />
    </v-main>
    <v-main v-else-if="itemsExist" id="browsePane">
      <BrowseCard
        v-for="item in objList"
        :key="`${item.group}${item.pk}`"
        :item="item"
      />
    </v-main>
    <v-main v-else-if="librariesExist" id="browsePane">
      <div id="noComicsFound">No comics found for these filters</div>
    </v-main>
    <v-main v-else id="browsePane">
      <div id="noLibraries">
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
  </div>
</template>

<script>
import { mdiArrowUp, mdiCloseCircle, mdiDotsVertical } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import { ADMIN_URL } from "@/api/auth";
import { getSocket } from "@/api/browser";
import AuthDialog from "@/components/auth-dialog";
import BrowseCard from "@/components/browse-card";
import FilterSubMenu from "@/components/filter-sub-menu";
import PlaceholderLoading from "@/components/placeholder-loading.vue";

export default {
  name: "Browser",
  components: {
    AuthDialog,
    BrowseCard,
    FilterSubMenu,
    PlaceholderLoading,
  },
  data() {
    return {
      mdiArrowUp,
      mdiDotsVertical,
      socket: undefined,
      adminURL: ADMIN_URL,
    };
  },
  computed: {
    ...mapState("browser", {
      browseTitle: (state) => state.browseTitle,
      currentRoute: (state) => state.routes.current,
      formChoices: (state) => state.formChoices,
      settings: (state) => state.settings,
      upRoute: (state) => state.routes.up,
      objList: (state) => state.objList,
      filterMode: (state) => state.filterMode,
      browseLoaded: (state) => state.browseLoaded,
      librariesExist: (state) => state.librariesExist,
      itemsExist: (state) => state.objList && state.objList.length > 0,
      versions: (state) => state.versions,
      scanNotify: (state) => state.scanNotify,
      numPages: (state) => state.numPages,
    }),
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    ...mapGetters("browser", ["rootGroupChoices", "filterNames"]),
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
    filterInnerIcon: function () {
      if (this.isFiltersClearable) {
        return mdiCloseCircle;
      }
      return " ";
    },
    filterMenuClass: function () {
      // Lets me hide bookmark menu items with css when the filterMode
      //   changes.
      let className = "filterMenu";
      if (this.filterMode !== "base") {
        className += "Hidden";
      }
      return className;
    },
    isOtherFiltersSelected: function () {
      for (let filterName of this.filterNames) {
        const filterArray = this.settings.filters[filterName];
        if (filterArray && filterArray.length > 0) {
          return true;
        }
      }
      return false;
    },
    isFiltersClearable: function () {
      if (this.bookmarkFilter !== "ALL") {
        return true;
      }
      return this.isOtherFiltersSelected;
    },
    showUpButton: function () {
      return this.upRoute && this.upRoute.group;
    },
    bookmarkFilter: {
      get() {
        return this.getFilter("bookmark");
      },
      set(value) {
        if (value === null || value === undefined) {
          console.warn(`bookmarkFilter was ${value}. Setting to 'ALL'`);
          value = "ALL";
        }
        this.setFilter("bookmark", value);
      },
    },
    decadeFilter: {
      get() {
        return this.getFilter("decade");
      },
      set(value) {
        this.setFilter("decade", value);
      },
    },
    charactersFilter: {
      get() {
        return this.getFilter("characters");
      },
      set(value) {
        this.setFilter("characters", value);
      },
    },
    rootGroup: {
      get() {
        return this.settings.rootGroup;
      },
      set(value) {
        this.settingChanged({ rootGroup: value });
      },
    },
    sortBy: {
      get() {
        return this.settings.sortBy;
      },
      set(value) {
        let data = {};
        if (value === this.settings.sortBy) {
          data.sortReverse = !this.settings.sortReverse;
        } else {
          data.sortReverse = false;
          data.sortBy = value;
        }
        this.settingChanged(data);
      },
    },
  },
  watch: {
    $route(newRoute) {
      this.$store.dispatch("browser/routeChanged", newRoute.params);
    },
    user() {
      this.$store.dispatch("browser/browseOpened", this.$route.params);
      if (this.isAdmin) {
        this.setScanNotify(false);
      }
    },
  },
  created() {
    this.$store.dispatch("browser/browseOpened", this.$route.params);
    this.socket = getSocket();
    this.socket.addEventListener("message", this.websocketListener);
  },
  beforeDestroy() {
    if (this.socket) {
      this.socket.close();
    }
  },
  methods: {
    websocketListener: function (event) {
      console.debug("websocket push:", event.data);
      if (event.data === "libraryChanged") {
        this.$store.dispatch("browser/getBrowseObjects");
      } else if (this.isAdmin && event.data === "scanLibrary") {
        this.setScanNotify(true);
      }
    },
    settingChanged: function (data) {
      this.$store.dispatch("browser/settingChanged", data);
    },
    setSubSetting: function (key, subKey, value) {
      const data = { [key]: { [subKey]: value } };
      this.settingChanged(data);
    },
    getShow: function (group) {
      return this.settings.show[group];
    },
    setShow: function (group, value) {
      this.setSubSetting("show", group, value === true);
    },
    getFilter: function (filterName) {
      return this.settings.filters[filterName];
    },
    setFilter: function (filterName, value) {
      this.setSubSetting("filters", filterName, value);
    },
    clearFilters: function () {
      this.$store.dispatch("browser/clearFilters");
    },
    closeFilterSelect: function () {
      // On click, reselect the current value to close the menu.
      const item = this.$refs.filterSelect.selectedItems[0];
      this.$refs.filterSelect.selectItem(item);
      this.$store.dispatch("browser/setFilterMode", { mode: "base" });
    },
    reload: function () {
      // this.$store.dispatch("browser/browseOpened", this.$route.params);
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
.toolbarSelect {
}
#browsePane {
  display: flex;
  margin-top: 96px;
  margin-left: 15px;
  overflow: auto;
}
.sortArrow {
  width: 20px;
  float: right;
}
.upsideDown {
  transform: rotate(180deg);
}
.invisible {
  visibility: hidden;
}
#filterSuffix {
  margin-left: 0.25em;
}
#settingsGroupCaption {
  color: gray;
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
.rootGroupSelect {
  width: 118px;
  margin-left: 8px;
  margin-right: 8px;
}
.sortBySelect {
  width: 168px;
}
#settingsMenu {
  background-color: #121212;
}
#progressBar {
  margin-top: 40px;
}
#noLibraries {
  text-align: center;
}
#scanNotify > .v-snack__wrapper {
  min-width: 183px;
}
.outdated {
  font-style: italic;
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
  .rootGroupSelect {
    width: 95px;
    margin-left: 4px;
    margin-right: 4px;
  }
  .sortBySelect {
    width: 133px;
    margin-right: -19px;
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
