<template>
  <v-main id="browsePane" :class="{ padFooter: padFooter }">
    <div v-if="showBrowseItems" id="browsePaneContainer">
      <BrowserCard
        v-for="item in cards"
        :key="`${item.group}${item.ids}`"
        :item="item"
      />
    </div>
    <PlaceholderLoading v-else-if="showPlaceHolder" class="placeholder" />
    <BrowserEmptyState v-else />
    <div
      v-if="searchLimitMessage"
      id="searchLimitMessage"
      title="You may change this in the settings drawer"
    >
      {{ searchLimitMessage }}
    </div>
  </v-main>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import BrowserCard from "@/components/browser/card/card.vue";
import BrowserEmptyState from "@/components/browser/empty.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserMain",
  components: {
    BrowserCard,
    BrowserEmptyState,
    PlaceholderLoading,
  },
  computed: {
    ...mapState(useAuthStore, {
      nonUsers: (state) => state.adminFlags.nonUsers,
    }),
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapGetters(useBrowserStore, ["isSearchMode"]),
    ...mapState(useBrowserStore, {
      librariesExist: (state) => state.page.librariesExist,
      showPlaceHolder(state) {
        return (
          this.nonUsers === undefined ||
          (this.isCodexViewable &&
            (this.librariesExist == undefined || !state.browserPageLoaded))
        );
      },
      //searchResultsLimit: (state) => state.settings.searchResultsLimit,
      cards: (state) => [
        ...(state.page.groups ?? []),
        ...(state.page.books ?? []),
      ],
      numPages: (state) => state.page.numPages,
      query: (state) => state.settings.q,
    }),
    padFooter() {
      return this.numPages > 1;
    },
    showBrowseItems() {
      return (
        this.cards &&
        this.cards.length > 0 &&
        this.isCodexViewable &&
        !this.showPlaceHolder
      );
    },
    searchLimitMessage() {
      let res = "";
      if (!this.query) {
        return res;
      }
      // if (this.isSearchLimitedMode) {
      const page = +this.$route.params.page;
      // const limit = this.searchResultsLimit * page;
      const limit = 100 * page;
      if (this.showPlaceHolder) {
        res += `Searching for ${limit} entries...`;
      } else if (this.numPages > page) {
        res += `Search results truncated to ${limit} entries.`;
        res += " Advance the page to look for more.";
      }
      /*
      } else if (this.isSearchMode) {
        res = "Select incremental search in the side bar to search faster";
      }
      */
      return res;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["loadBrowserPage"]),
    refresh() {
      this.loadBrowserPage();
    },
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
#searchLimitMessage {
  padding-top: 20px;
  text-align: center;
  font-size: 14px;
  color: rgb(var(--v-theme-textDisabled));
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
}
</style>
