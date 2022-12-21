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
      <PlaceholderLoading class="placeholder" />
    </div>
    <div v-else-if="!isCodexViewable" id="announce">
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
      <h2 v-if="isUserAdmin">
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
        >See the README <v-icon>{{ mdiOpenInNew }}</v-icon></a
      >
      for detailed instructions.
    </div>
  </v-main>
</template>

<script>
import { mdiMenu, mdiOpenInNew } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import BrowserCard from "@/components/browser/card/card.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserMain",
  components: {
    BrowserCard,
    PlaceholderLoading,
  },
  data() {
    return {
      mdiMenu,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      enableNonUsers: (state) => state.adminFlags.enableNonUsers,
      enableRegister: (state) => state.adminFlags.enableRegistration,
    }),
    ...mapGetters(useAuthStore, ["isUserAdmin", "isCodexViewable"]),
    ...mapState(useBrowserStore, {
      objList: (state) => state.page.objList,
      librariesExist: (state) => state.page.librariesExist,
      padFooter: (state) => state.page.numPages > 1,
      showBrowseItems: function (state) {
        return (
          state.page.objList &&
          state.page.objList.length > 0 &&
          this.isCodexViewable &&
          !this.showPlaceHolder
        );
      },
      showPlaceHolder: function (state) {
        return (
          this.enableNonUsers === undefined ||
          (this.isCodexViewable &&
            (this.librariesExist == undefined || !state.browserPageLoaded))
        );
      },
    }),
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@import "../book-cover.scss";
$card-margin: 32px;
#browsePane {
  margin-top: 160px;
  margin-left: max($card-margin, env(safe-area-inset-left));
  margin-right: max($card-margin, env(safe-area-inset-right));
  margin-bottom: max($card-margin, env(safe-area-inset-bottom));
  overflow: auto;
}
#browsePaneContainer {
  margin-top: $card-margin;
  display: grid;
  grid-template-columns: repeat(auto-fit, $cover-width);
  grid-gap: $card-margin;
  align-content: flex-start;
}
#announce {
  text-align: center;
}
#noComicsFound {
  font-size: x-large;
  padding: 1em;
  color: rbg(var(--v-theme-textDisabled));
}
.padFooter {
  padding-bottom: 45px !important;
}
.placeholder {
  position: fixed;
  height: 50vh !important;
  width: 50vw !important;
  top: calc(50% + 75px);
  left: 50%;
  transform: translate(-50%, -50%);
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  $small-card-margin: 16px;
  #browsePane {
    margin-left: max($small-card-margin, env(safe-area-inset-left));
    margin-right: max($small-card-margin, env(safe-area-inset-right));
    margin-bottom: max($small-card-margin, env(safe-area-inset-bottom));
  }

  #browsePaneContainer {
    grid-template-columns: repeat(auto-fit, $small-cover-width);
    grid-gap: $small-card-margin;
    justify-content: space-evenly;
  }
  #noComicsFound {
    font-size: large;
  }
}
</style>
