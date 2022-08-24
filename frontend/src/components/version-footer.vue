<template>
  <v-footer id="versionFooter">
    <div id="version" :class="{ outdated: outdated }">
      codex v{{ versions.installed }}
    </div>
    <div v-if="outdated">codex v{{ versions.latest }} is available</div>
    <a id="repo" href="https://github.com/ajslater/codex" :title="versionTitle">
      repository<v-icon color="grey" dense x-small>{{ mdiOpenInNew }}</v-icon>
    </a>
  </v-footer>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

export default {
  name: "VersionFooter",
  data() {
    return {
      mdiOpenInNew,
    };
  },
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
  created() {
    this.$store.dispatch("browser/getVersions");
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
#version {
}
#repo {
  color: gray;
}
#repo:hover {
  color: white;
}
#versionFooter * {
  width: 100%;
}
.outdated {
  font-style: italic;
}
</style>
