<template>
  <v-window id="pageWindow" v-model="windowPage" show-arrows @change="change">
    <template #prev="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <template #next="{ on, attrs }">
      <div class="navColumn" v-bind="attrs" v-on="on"></div>
    </template>
    <v-window-item
      v-for="page in maxPage"
      :key="page"
      class="windowItem"
      @click="$emit('click')"
    >
      <img
        class="page"
        :src="getSrc(page)"
        :class="fitToClass"
        :alt="`Page ${page}`"
      />
      <img
        v-if="secondPage"
        class="page"
        :src="getSrc(page + 1)"
        :class="fitToClass"
        :alt="`Page ${page + 1}`"
      />
    </v-window-item>
  </v-window>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

//const PLACEHOLDER_ENGAGE_MS = 500;
//const TOOLBAR_HEIGHT = 48;

export default {
  name: "ReaderWindow",
  props: {},
  data() {
    return {
      windowPage: 0,
    };
  },
  head() {
    if (this.prefetchHref) {
      return {
        lnk: [{ rel: "prefetch", as: "image", href: this.prefetchHref }],
      };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      maxPage: (state) => state.comic.maxPage,
      nextRoute: (state) => state.routes.next,
      timestamp: (state) => state.timestamp,
      secondPage(state) {
        return (
          state.computedSettings.twoPages &&
          +this.windowPage + 1 <= state.comic.maxPage
        );
      },
    }),
    ...mapGetters(useReaderStore, ["computedSettings"]),
    prefetchHref() {
      if (!this.nextRoute) {
        return;
      }
      return getComicPageSource(this.nextRoute, this.timestamp);
    },
    fitToClass() {
      let classes = {};
      const fitTo = this.computedSettings.fitTo;
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass += fitTo.charAt(0).toUpperCase();
        fitToClass += fitTo.slice(1).toLowerCase();
        if (this.computedSettings.twoPages) {
          fitToClass += "Two";
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
  },
  watch: {
    $route: function () {
      console.log("route changed");
      this.setPage();
    },
  },
  created: function () {
    this.setPage();
  },
  methods: {
    ...mapActions(useReaderStore, ["routeToPage"]),
    getSrc(page) {
      const routeParams = { ...this.$router.currentRoute.params, page };
      return getComicPageSource(routeParams, this.timestamp);
    },
    setPage: function () {
      this.windowPage = +this.$router.currentRoute.params.page;
    },
    change(page) {
      this.routeToPage(page);
    },
  },
};
</script>

<style scoped lang="scss">
.navColumn {
  width: 100%;
  height: 100%;
}
.windowItem {
  text-align: center;
  height: 100vh;
}
.fitToScreen,
.fitToScreenTwo {
  max-height: 100vh;
}
.fitToScreen {
  max-width: 100vw;
}
.fitToHeight,
.fitToHeightTwo {
  height: 100vh;
}
.fitToWidth {
  width: 100vw;
}
.fitToWidthTwo {
  width: 50vw;
}
.fitToScreenTwo {
  max-width: 50vw;
}
.fitToOrig,
.fitToOrigTwo {
  object-fit: none;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#pageWindow .v-window__prev,
#pageWindow .v-window__next {
  top: 48px;
  width: 33vw;
  height: calc(100vh - 96px);
  opacity: 0.2;
}
#pageWindow .v-window__prev {
  cursor: w-resize;
}
#pageWindow .v-window__next {
  cursor: e-resize;
}
</style>
