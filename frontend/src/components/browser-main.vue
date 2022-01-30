<template>
  <v-main id="browsePane" :class="{ padFooter: padFooter }">
    <div v-if="showBrowseItems">
      <BrowserCard
        v-for="item in objList"
        :key="`${item.group}${item.pk}`"
        :item="item"
      />
    </div>
    <div v-else-if="showPlaceHolder" id="announce">
      <PlaceholderLoading />
    </div>
    <div v-else-if="!isOpenToSee" id="announce">
      <h1>
        You may log in or register with the top right
        <v-icon>{{ mdiMenu }}</v-icon
        >menu
      </h1>
    </div>
    <div v-else-if="librariesExist" id="announce">
      <div id="noComicsFound">No comics found for these filters</div>
    </div>
    <div v-else id="announce">
      <h1>No libraries have been added to Codex yet</h1>
      <h2 v-if="isAdmin">
        Use the top right <v-icon>{{ mdiMenu }}</v-icon> menu to navigate to the
        admin panel and add a comic library.
      </h2>
      <div v-else>
        <h2>
          An administrator must login to add some libraries that contain comics
        </h2>
        <h3>
          You may log in or register with the top right
          <v-icon>{{ mdiMenu }}</v-icon
          >menu
        </h3>
      </div>
      <a
        href="https://github.com/ajslater/codex#-administration"
        target="_blank"
        >See the README</a
      >
      for detailed instructions.
    </div>
  </v-main>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import BrowserCard from "@/components/browser-card";
import PlaceholderLoading from "@/components/placeholder-loading";

export default {
  name: "BrowserMain",
  components: {
    BrowserCard,
    PlaceholderLoading,
  },
  data() {
    return {
      mdiMenu,
    };
  },
  computed: {
    ...mapState("browser", {
      objList: (state) => state.objList,
      librariesExist: (state) => state.librariesExist,
      padFooter: (state) => state.numPages > 1,
      showBrowseItems: function (state) {
        return (
          state.objList &&
          state.objList.length > 0 &&
          this.isOpenToSee &&
          !this.showPlaceHolder
        );
      },
      showPlaceHolder: function (state) {
        return (
          this.enableNonUsers === undefined ||
          (!state.browserPageLoaded && this.isOpenToSee)
        );
      },
    }),
    ...mapState("auth", {
      enableNonUsers: (state) => state.enableNonUsers,
    }),
    ...mapGetters("auth", ["isAdmin", "isOpenToSee"]),
    outdated: function () {
      return this.versions.latest > this.versions.installed;
    },
  },
};
</script>

<style scoped lang="scss">
#browsePane {
  display: flex;
  margin-top: 160px;
  margin-left: 15px;
  overflow: auto;
}
#announce {
  text-align: center;
}
#noComicsFound {
  font-size: x-large;
  padding: 1em;
  color: gray;
}
.padFooter {
  padding-bottom: 45px !important;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #noComicsFound {
    font-size: large;
  }
}
</style>
