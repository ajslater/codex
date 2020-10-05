<template>
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
</template>

<script>
import { mapState } from "vuex";

export default {
  name: "Browser",
  computed: {
    ...mapState("browser", {
      numPages: (state) => state.numPages,
      versions: (state) => state.versions,
    }),
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
  },
  methods: {
    routeToPage: function (page) {
      const route = {
        name: this.$route.name,
        params: { ...this.$route.params },
      };
      route.params.page = page;
      this.$router.push(route);
    },
  },
};
</script>

<style scoped lang="scss">
.invisible {
  visibility: hidden;
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
.outdated {
  font-style: italic;
}
</style>
