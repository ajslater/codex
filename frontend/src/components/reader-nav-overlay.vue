<template>
  <div id="navColumns">
    <v-navigation-drawer
      v-if="!routePrevPage && routePrevBook"
      id="prevBookDrawer"
      class="bookChangeDrawer"
      absolute
      left
      temporarary
      :value="bookChangePrev"
    >
      <router-link class="navLink" :to="routePrevBook">
        <v-icon class="bookChangeIcon flipped" x-large>{{
          mdiBookArrowRight
        }}</v-icon>
      </router-link>
    </v-navigation-drawer>
    <section id="leftColumn" class="navColumn" @click.stop>
      <router-link v-if="routePrevPage" class="navLink" :to="routePrevPage" />
      <div
        v-else-if="routePrevBook"
        class="drawerButton"
        @click="setBookChangeFlag('prev')"
      />
    </section>
    <section
      id="middleColumn"
      class="navColumn"
      @click="setBookChangeFlag(null)"
    />
    <section id="rightColumn" class="navColumn" @click.stop>
      <router-link v-if="routeNextPage" class="navLink" :to="routeNextPage" />
      <div
        v-else-if="routeNextBook"
        class="drawerButton"
        @click.stop="setBookChangeFlag('next')"
      />
    </section>
    <v-navigation-drawer
      v-if="!routeNextPage && routeNextBook"
      id="nextBookDrawer"
      class="bookChangeDrawer"
      absolute
      right
      temporarary
      :value="bookChangeNext"
    >
      <router-link class="navLink" :to="routeNextBook" @click.native.stop>
        <v-icon class="bookChangeIcon" x-large>{{ mdiBookArrowRight }}</v-icon>
      </router-link>
    </v-navigation-drawer>
  </div>
</template>

<script>
import { mdiBookArrowRight } from "@mdi/js";
import { mapActions, mapState } from "vuex";
const PREV = "prev";
const NEXT = "next";

export default {
  name: "ReaderNavOverlay",
  data() {
    return { mdiBookArrowRight };
  },
  computed: {
    ...mapState("reader", {
      routes: (state) => state.routes,
      bookChangePrev: (state) => state.bookChange === PREV,
      bookChangeNext: (state) => state.bookChange === NEXT,
    }),
    routePrevPage: function () {
      return this.toRoute("prev");
    },
    routeNextPage: function () {
      return this.toRoute("next");
    },
    routePrevBook: function () {
      return this.toRoute("prevBook");
    },
    routeNextBook: function () {
      return this.toRoute("nextBook");
    },
  },
  mounted() {
    // Keyboard Shortcuts
    window.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions("reader", ["routeToDirection", "setBookChangeFlag"]),
    toRoute: function (name) {
      const params = this.routes[name];
      if (!params) {
        return false;
      }
      return { name: "reader", params };
    },
    _keyListener: function (event) {
      switch (event.key) {
        case " ":
          if (
            !event.shiftKey &&
            window.innerHeight + window.scrollY >= document.body.scrollHeight &&
            this.routes.next
          ) {
            // Spacebar goes next only at the bottom of page
            this.routeToDirection(NEXT);
          } else if (
            // Shift + Spacebar goes back only at the top of page
            !!event.shiftKey &&
            window.scrollY === 0 &&
            this.routes.prev
          ) {
            this.routeToDirection(PREV);
          }
          break;
        case "j":
        case "ArrowRight":
          this.routeToDirection(NEXT);
          break;

        case "k":
        case "ArrowLeft":
          this.routeToDirection(PREV);
          break;
        // No default
      }
    },
  },
};
</script>

<style scoped lang="scss">
#navColumns {
  width: 100%;
  height: 100%;
  padding-top: 48px;
  padding-bottom: 48px;
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
.drawerButton {
  height: 100%;
  cursor: grab;
}
.bookChangeDrawer {
  background-color: rgba(0, 0, 0, 0.3);
}
.bookChangeIcon {
  top: 50%;
  margin-left: 50%;
  display: block;
  color: white;
}
.flipped {
  transform: rotateY(180deg);
}
</style>
