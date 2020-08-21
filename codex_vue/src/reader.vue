<template>
  <v-container
    id="readerContainer"
    v-touch="{
      left: () => routeToNext(),
      right: () => routeToPrev(),
    }"
    fluid
    style="margin: 0; padding: 0;"
  >
    <nav id="navOverlay">
      <div class="toolbarClick" @click="toggleToolbars()" />
      <div id="navColumns">
        <section id="leftColumn" class="navColumn">
          <router-link
            v-if="routes.prev"
            :to="{ name: 'reader', params: routes.prev }"
            class="navLink"
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
            :to="{ name: 'reader', params: routes.next }"
            class="navLink"
          />
        </section>
      </div>
      <div class="toolbarClick" @click="toggleToolbars()" />
    </nav>

    <main id="pagesContainer">
      <transition appear :name="pageSlideDirection">
        <div id="pages">
          <ReaderComicPage :page="+0" />
          <ReaderComicPage v-if="twoPages" :page="+1" />
        </div>
      </transition>
    </main>

    <v-slide-y-transition>
      <v-toolbar
        v-show="showToolbars"
        horizontal
        dense
        elevation="1"
        width="100%"
        style="position: fixed; top: 0px;"
      >
        <v-btn id="closeBook" :to="{ name: 'browser', params: browseRoute }"
          >close book</v-btn
        >
        <v-spacer />
        <v-toolbar-title>{{ title }}</v-toolbar-title>
        <v-spacer />
        <v-dialog
          origin="center top"
          transition="slide-y-transition"
          max-width="20em"
          overlay-opacity="0.5"
        >
          <template v-slot:activator="{ on }">
            <v-btn icon v-on="on">
              <v-icon>{{ mdiCog }}</v-icon>
            </v-btn>
          </template>
          <v-radio-group id="fitToSelect" v-model="fitTo" label="Shrink to">
            <v-radio
              v-for="item in staticFormChoices.fitToChoices"
              :key="item.value"
              :label="item.text"
              :value="item.value"
            />
          </v-radio-group>
          <label>Display</label>
          <v-checkbox v-model="twoPages" label="Two pages" ripple />
          <v-btn ripple @click="defaultSettingChanged()">make default</v-btn>
        </v-dialog>
        <MetadataDialog ref="metadataDialog" :pk="pk" />
      </v-toolbar>
    </v-slide-y-transition>

    <v-slide-y-reverse-transition>
      <v-toolbar
        v-show="showToolbars"
        id="navFooter"
        horizontal
        dense
        elevation="1"
        width="100%"
        transform="center bottom"
        style="position: fixed; bottom: 0px;"
      >
        <ReaderNavButton :value="0" />
        <v-slider
          id="slider"
          :value="pageNumber"
          min.number="+0"
          :max="maxPage"
          thumb-label="always"
          ticks="always"
          hide-detail
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
import { mapState } from "vuex";

import FORM_CHOICES from "@/choices/readerChoices.json";
import MetadataDialog from "@/components/metadata-dialog.vue";
import ReaderComicPage from "@/components/reader-comic-page.vue";
import ReaderNavButton from "@/components/reader-nav-button.vue";

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
      pageSlideDirection: "slide-right",
      staticFormChoices: FORM_CHOICES,
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
    }),
    ...mapState("browser", {
      browseRoute: (state) => state.routes.current || { group: "p", pk: 0 },
    }),
    pageSlideKey: function () {
      // TODO page left animations aren't good. probably a key issue.
      return `${this.pk}:${this.pageNumber}`;
    },
    twoPages: {
      get() {
        return this.settings.twoPages;
      },
      set(value) {
        this.settingChanged({ twoPages: value === true });
      },
    },
    fitTo: {
      get() {
        return this.settings.fitTo;
      },
      set(value) {
        this.settingChanged({ fitTo: value });
      },
    },
  },
  watch: {
    $route(to, from) {
      let action = "reader/";
      if (
        to.params.pk < from.params.pk ||
        to.params.pageNumber < from.params.pageNumber
      ) {
        this.pageSlideDirection = "slide-left";
      } else {
        this.pageSlideDirection = "slide-right";
      }
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
        this.settingChanged({ fitTo: "WIDTH" });
      } else if (event.key === "h") {
        this.settingChanged({ fitTo: "HEIGHT" });
      } else if (event.key === "o") {
        this.settingChanged({ fitTo: "ORIG" });
      } else if (event.key === "2") {
        this.settingChanged({ twoPages: !this.twoPages });
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
    settingChanged: function (data) {
      this.$store.dispatch("reader/settingChanged", data);
    },
    defaultSettingChanged: function () {
      this.$store.dispatch("reader/defaultSettingsChanged");
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
/* NAV COLUMNS */
#navOverlay {
  position: fixed;
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
/* TODO RIGHT SCROLL */
#pagesContainer {
  text-align: center;
}
#pages {
  margin: auto;
  white-space: nowrap;
}

.slide-right-enter,
.slide-left-leave {
  -webkit-transform: translateX(100vw);
  -moz-transform: translateX(100vw);
  -o-transform: translateX(100vw);
  transition: translateX(100vw);
}
.slide-right-leave-active,
.slide-left-enter-active {
  -webkit-transform: translateX(-100vw);
  -moz-transform: translateX(-100vw);
  -o-transform: translateX(-100vw);
  transition: translateX(-100vw);
}
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.1s ease-in;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
/* TOOLBARS */
.v-dialog {
  /* Seems like I'm fixing a bug here */
  background: #121212;
  padding: 20px;
}
/* Custom slider with a large control. */
.v-input__slider .v-slider__thumb {
  height: 24px;
  width: 24px;
  left: -12px;
}
.v-input__slider .v-slider__thumb::before {
  left: -6px;
  top: -6px;
}
</style>
