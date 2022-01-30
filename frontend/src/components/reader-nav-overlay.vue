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
import { mapState } from "vuex";

export default {
  name: "ReaderNavOverlay",
  computed: {
    ...mapState("reader", {
      routes: (state) => state.routes,
    }),
  },
  mounted() {
    // Keyboard Shortcuts
    window.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },

  methods: {
    _keyListener: function (event) {
      switch (event.key) {
        case "j":
        case "ArrowRight":
          this.$store.dispatch("reader/routeTo", "next");
          break;

        case "k":
        case "ArrowLeft":
          this.$store.dispatch("reader/routeTo", "prev");
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
</style>
