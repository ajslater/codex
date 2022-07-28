<template>
  <v-main id="browsePane" :class="{ padFooter: padFooter }">
    <div v-if="showBrowseItems" id="browsePaneContainer">
      <BrowserCard
        v-for="item in objList"
        :key="`${item.group}${item.pk}`"
        :item="item"
      />
    </div>
    <div v-else-if="showPlaceHolder" id="announce">
      <PlaceholderLoading class="placeholder" :size="128" />
    </div>
    <div v-else-if="!isOpenToSee" id="announce">
      <h1>
        You may log in <span v-if="enableRegister">or register</span> with the
        top right&emsp;<v-icon>{{ mdiMenu }}</v-icon
        >&emsp;menu
      </h1>
      <h1 v-if="!enableRegister">Registration is disabled</h1>
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
      enableNonUsers: (state) => state.adminFlags.enableNonUsers,
      enableRegister: (state) => state.adminFlags.enableRegistration,
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
  margin-left: max(16px, env(safe-area-inset-left));
  margin-right: max(16px, env(safe-area-inset-right));
  overflow: auto;
}
#browsePaneContainer {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fit, 120px);
  grid-gap: 32px;
  justify-content: start;
  align-content: flex-start;
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
.placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #browsePaneContainer {
    grid-template-columns: repeat(auto-fit, 100px);
    grid-gap: 16px;
    justify-content: space-evenly;
  }
  #noComicsFound {
    font-size: large;
  }
}
</style>
