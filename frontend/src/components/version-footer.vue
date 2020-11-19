<template>
  <v-footer id="versionFooter">
    <a
      id="versionFooter"
      href="https://github.com/ajslater/codex"
      :title="versionTitle"
      :class="{ outdated: outdated }"
      >codex v{{ versions.installed }}
      <div v-if="outdated">codex v{{ versions.latest }} is available</div>
    </a>
  </v-footer>
</template>

<script>
import { mapGetters, mapState } from "vuex";

export default {
  name: "VersionFooter",
  computed: {
    ...mapState("browser", {
      numPages: (state) => state.numPages,
      versions: (state) => state.versions,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    outdated: function () {
      return this.isAdmin && this.versions.latest > this.versions.installed;
    },
    versionTitle: function () {
      return this.outdated
        ? `v${this.versions.latest} is availble`
        : "up to date";
    },
  },
};
</script>

<style scoped lang="scss">
#versionFooter {
  width: 100%;
  text-align: center;
  font-size: small;
  color: gray;
}
.outdated {
  font-style: italic;
}
</style>
