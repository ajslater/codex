<template>
  <div id="readerWrapper">
    <div v-if="isOpenToSee" id="readerContainer">
      <v-main>
        <div id="pagesContainer">
          <ReaderComicPage :page-increment="+0" />
          <ReaderComicPage :page-increment="+1" />
        </div>
      </v-main>
      <nav
        id="navOverlay"
        v-touch="{
          left: () => $store.dispatch('reader/routeTo', 'next'),
          right: () => $store.dispatch('reader/routeTo', 'prev'),
        }"
        @click="toggleToolbars()"
      >
        <ReaderNavOverlay />
      </nav>
      <v-slide-y-transition>
        <ReaderTopToolbar v-show="showToolbars" />
      </v-slide-y-transition>
      <v-slide-y-reverse-transition>
        <ReaderNavToolbar v-show="showToolbars" />
      </v-slide-y-reverse-transition>
    </div>
    <div v-else id="announcement">
      <h1>
        <router-link :to="{ name: 'home' }">Log in</router-link> to read comics
      </h1>
    </div>
  </div>
</template>

<script>
import { mapGetters } from "vuex";

import ReaderComicPage from "@/components/reader-comic-page";
import ReaderNavOverlay from "@/components/reader-nav-overlay";
import ReaderNavToolbar from "@/components/reader-nav-toolbar";
import ReaderTopToolbar from "@/components/reader-top-toolbar";

export default {
  name: "MainReader",
  components: {
    ReaderComicPage,
    ReaderNavOverlay,
    ReaderNavToolbar,
    ReaderTopToolbar,
  },
  data() {
    return {
      showToolbars: false,
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    $route(to, from) {
      let action = "reader/";
      action +=
        +to.params.pk !== +from.params.pk ? "bookChanged" : "routeChanged";
      this.$store.dispatch(action, {
        pk: +to.params.pk,
        page: +to.params.page,
      });
      window.scrollTo(0, 0);
    },
  },
  created() {
    const params = {
      // Cast the route params as numbers
      pk: +this.$route.params.pk,
      page: +this.$route.params.page,
    };
    this.$store.dispatch("reader/readerOpened", params);
  },
  methods: {
    toggleToolbars: function () {
      this.showToolbars = !this.showToolbars;
    },
  },
};
</script>

<style scoped lang="scss">
#navOverlay {
  position: fixed;
  top: 0px;
  width: 100%;
  height: 100vh;
}
#pagesContainer {
  /* because its more difficult to center with v-main */
  display: flex;
  flex-wrap: nowrap;
  justify-content: center;
}
#readerContainer {
  padding: 0px;
  max-width: 100%;
}
#announcement {
  text-align: center;
}
</style>
