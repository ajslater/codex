<template>
  <v-container id="readerContainer">
    <v-main id="pagesContainer">
      <div id="pages">
        <ReaderComicPage :page="+0" />
        <ReaderComicPage :page="+1" />
      </div>
    </v-main>

    <nav id="navOverlay">
      <div class="toolbarClick" @click="toggleToolbars()" />
      <div id="navColumns">
        <section id="leftColumn" class="navColumn">
          <router-link
            v-if="routes.prev"
            class="navLink"
            :to="{ name: 'reader', params: routes.prev }"
          />
        </section>
        <section
          id="middleColumn"
          class="navColumn"
          @click="toggleToolbars()"
        />
        <section id="rightColumn" class="navColumn">
          <router-link
            v-if="routes.next"
            class="navLink"
            :to="{ name: 'reader', params: routes.next }"
          />
        </section>
      </div>
      <div class="toolbarClick" @click="toggleToolbars()" />
    </nav>
    <v-slide-y-transition>
      <v-toolbar v-show="showToolbars" id="topToolbar" class="toolbar" dense>
        <v-btn
          id="closeBook"
          :to="{ name: 'browser', params: browseRoute }"
          large
          ripple
          >close book</v-btn
        >
        <v-spacer />
        <v-toolbar-title>{{ title }}</v-toolbar-title>
        <v-spacer />
        <v-dialog
          class="readerSettings"
          origin="center top"
          transition="slide-y-transition"
          overlay-opacity="0.5"
        >
          <template #activator="{ on }">
            <v-btn icon v-on="on">
              <v-icon>{{ mdiCog }}</v-icon>
            </v-btn>
          </template>
          <h2>Reader Settings</h2>
          <v-radio-group
            id="fitToSelect"
            :value="settingsDialogFitTo"
            label="Shrink to"
            @change="settingDialogChanged({ fitTo: $event })"
          >
            <v-radio
              v-for="item in fitToChoices"
              :key="item.value"
              :label="item.text"
              :value="item.value"
            />
          </v-radio-group>
          <v-checkbox
            :value="settingsDialogTwoPages"
            label="Display Two pages"
            ripple
            @change="settingDialogChanged({ twoPages: $event })"
          />
          <v-switch
            v-model="isSettingsDialogGlobalMode"
            :label="settingsDialogSwitchLabel"
          />
          <v-btn
            :class="{ invisible: isSettingsDialogGlobalMode }"
            title="Use the global settings for all comics for this comic"
            @click="settingDialogClear()"
            >Clear Settings</v-btn
          >
        </v-dialog>
        <MetadataDialog ref="metadataDialog" :pk="pk" />
      </v-toolbar>
    </v-slide-y-transition>

    <v-slide-y-reverse-transition>
      <v-toolbar
        v-show="showToolbars"
        id="bottomToolbar"
        class="toolbar"
        dense
        transform="center bottom"
      >
        <ReaderNavButton :value="0" />
        <v-slider
          id="slider"
          :value="pageNumber"
          min.number="+0"
          :max="maxPage"
          thumb-label
          hide-details="auto"
          dense
          @change="routeTo({ pk, pageNumber: $event })"
        />
        <ReaderNavButton :value="maxPage" />
      </v-toolbar>
    </v-slide-y-reverse-transition>
  </v-container>
</template>

<script>
import { mdiCog } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import MetadataDialog from "@/components/metadata-dialog.vue";
import ReaderComicPage from "@/components/reader-comic-page.vue";
import ReaderNavButton from "@/components/reader-nav-button.vue";
const DEFAULT_ROUTE = { group: "p", pk: 0 };

export default {
  name: "Reader",
  components: {
    ReaderComicPage,
    ReaderNavButton,
    MetadataDialog,
  },
  data() {
    return {
      mdiCog,
      showToolbars: false,
      isSettingsDialogGlobalMode: false,
    };
  },
  computed: {
    ...mapState("reader", {
      title: (state) => state.title,
      maxPage: (state) => state.maxPage,
      routes: (state) => state.routes,
      settings: (state) => state.settings,
      pk: (state) => state.routes.current.pk,
      pageNumber: (state) => state.routes.current.pageNumber,
      fitToChoices: (state) => state.formChoices.fitTo,
      settingsScope: function (state) {
        if (this.isSettingsDialogGlobalMode) {
          return state.settings.globl;
        }
        return state.settings.local;
      },
    }),
    ...mapState("browser", {
      browseRoute: (state) => state.routes.current || DEFAULT_ROUTE,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    settingsDialogTwoPages: function () {
      return this.settingsScope.twoPages;
    },
    settingsDialogFitTo: function () {
      return this.settingsScope.fitTo;
    },
    settingsDialogSwitchLabel: function () {
      let label = "For ";
      if (this.isSettingsDialogGlobalMode) {
        label += "All Comics";
      } else {
        label += "This Comic";
      }
      return label;
    },
  },
  watch: {
    $route(to, from) {
      let action = "reader/";
      if (+to.params.pk !== +from.params.pk) {
        action += "bookChanged";
      } else {
        action += "pageChanged";
      }
      this.$store.dispatch(action, {
        pk: +to.params.pk,
        pageNumber: +to.params.pageNumber,
      });
    },
  },
  beforeCreate() {
    this.$store.dispatch("reader/readerOpened", {
      // Cast the route params as numbers
      pk: +this.$route.params.pk,
      pageNumber: +this.$route.params.pageNumber,
    });
  },
  created() {
    this.createPrefetches();
  },
  mounted() {
    // Keyboard Shortcuts
    this._keyListener = function (event) {
      if (event.key === "ArrowLeft") {
        this.routeToPrev();
      } else if (event.key === "ArrowRight") {
        this.routeToNext();
      } else if (event.key === "Escape") {
        const mdd = this.$refs.metadataDialog;
        if (mdd.isOpen) {
          mdd.isOpen = false;
        } else {
          document.querySelector("#closeBook").click();
        }
      } else if (event.key === "w") {
        this.settingChangedLocal({ fitTo: "WIDTH" });
      } else if (event.key === "h") {
        this.settingChangedLocal({ fitTo: "HEIGHT" });
      } else if (event.key === "o") {
        this.settingChangedLocal({ fitTo: "ORIG" });
      } else if (event.key === "2") {
        this.settingChangedLocal({ twoPages: !this.twoPages });
      }
    };
    document.addEventListener("keyup", this._keyListener.bind(this));
  },
  beforeDestroy: function () {
    this.destroyPrefetches();
    document.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    routeTo: function (page) {
      if (!page) {
        return;
      }
      if (page.pk === this.pk) {
        if (page.pageNumber === this.pageNumber) {
          return;
        }
        if (page.pageNumber > this.maxPage) {
          page.maxPage = this.maxPage;
        }
      }
      if (page.pageNumber < 0) {
        page.pageNumber = 0;
      }
      this.$router.push({
        name: "reader",
        params: page,
      });
    },
    toggleToolbars: function () {
      this.showToolbars = !this.showToolbars;
    },
    routeToPrev: function () {
      this.routeTo(this.routes.prev);
    },
    routeToNext: function () {
      this.routeTo(this.routes.next);
    },
    settingChangedLocal: function (data) {
      this.$store.dispatch("reader/settingChangedLocal", data);
    },
    settingDialogChanged: function (data) {
      console.log("settingsDialogChanged", data);
      if (this.isSettingsDialogGlobalMode) {
        this.$store.dispatch("reader/settingChangedGlobal", data);
      } else {
        this.settingChangedLocal(data);
      }
    },
    settingDialogClear: function () {
      const data = {
        fitTo: null,
        twoPages: null,
      };
      this.settingChangedLocal(data);
    },
    createPrefetch(id) {
      const node = document.createElement("link");
      node.id = id;
      node.rel = "prefetch";
      node.as = "image";
      return node;
    },
    createPrefetches: function () {
      const node1 = this.createPrefetch("nextPage");
      const node2 = this.createPrefetch("next2Page");
      document.head.append(node1, node2);
    },
    destroyPrefetches() {
      for (const id of ["nextPage", "next2Page"]) {
        document.querySelector(`#${id}`).remove();
      }
    },
  },
};
</script>

<style scoped lang="scss">
#readerContainer {
  margin: 0px;
  padding: 0px;
}
/* NAV COLUMNS */
#navOverlay {
  position: fixed;
  top: 0px;
  width: 100%;
  height: 100vh;
}
.toolbarClick {
  width: 100%;
  height: 48px;
}
#navColumns {
  width: 100%;
  height: 100%;
}
.navColumn {
  float: left;
  width: 25%;
  height: 100%;
}
#middleColumn {
  width: 50%;
}
.navLink {
  display: block;
  height: 100%;
}

/* PAGES */
#pagesContainer {
  text-align: center;
}
#pages {
  margin: auto;
  white-space: nowrap;
}

.toolbar {
  width: 100%;
  position: fixed;
}
#topToolbar {
  top: 0px;
}
#bottomToolbar {
  bottom: 0px;
}
.invisible {
  visibility: hidden;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
/* TOOLBARS */
.toolbar .v-toolbar__content {
  padding: 0px;
}
#topToolbar > .v-toolbar__content {
  padding-right: 16px;
}
.v-dialog {
  padding: 20px;
  width: fit-content;
  /* Seems like I'm fixing a bug here */
  background: #121212;
}
/* Custom slider with a large control. */
.v-input__slider .v-slider__thumb {
  height: 48px;
  width: 48px;
  left: -24px;
}
.v-input__slider .v-slider__thumb::before {
  left: -8px;
  top: -8px;
  height: 64px;
  width: 64px;
}
</style>
