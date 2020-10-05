<template>
  <div id="navColumns">
    <section id="leftColumn" class="navColumn">
      <router-link
        v-if="routes.prev"
        class="navLink"
        :to="{ name: 'reader', params: routes.prev }"
        @click.native.stop=""
      />
    </section>
    <section id="middleColumn" class="navColumn" />
    <section id="rightColumn" class="navColumn">
      <router-link
        v-if="routes.next"
        class="navLink"
        :to="{ name: 'reader', params: routes.next }"
        @click.native.stop=""
      />
    </section>
  </div>
</template>

<script>
import { mapGetters, mapState } from "vuex";

export default {
  name: "ReaderNavOverlay",
  computed: {
    ...mapState("reader", {
      routes: (state) => state.routes,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  mounted() {
    // Keyboard Shortcuts
    document.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    document.removeEventListener("keyup", this._keyListener);
  },

  methods: {
    _keyListener: function (event) {
      // XXX Hack to get around too many listeners being added.
      event.stopPropagation();

      if (event.key === "ArrowLeft") {
        this.$store.dispatch("reader/routeTo", "prev");
      } else if (event.key === "ArrowRight") {
        this.$store.dispatch("reader/routeTo", "next");
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
</style>
