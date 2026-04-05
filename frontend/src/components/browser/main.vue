<template>
  <v-main id="browsePane" :class="browsePaneClasses">
    <v-pull-to-refresh
      v-if="showBrowseItems"
      id="browsePaneRefreshContainer"
      :pull-down-threshold="64"
      @load="load"
    >
      <BrowserCard
        v-for="item in cards"
        :key="`${item.group}${item.ids}`"
        :item="item"
      />
    </v-pull-to-refresh>
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
import { mapActions, mapState } from "pinia";

import BrowserCard from "@/components/browser/card/card.vue";
import BrowserEmptyState from "@/components/browser/empty.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useSelectManyStore } from "@/stores/select-many";
import { VPullToRefresh } from "vuetify/labs/VPullToRefresh";

export default {
  name: "BrowserMain",
  components: {
    BrowserCard,
    BrowserEmptyState,
    PlaceholderLoading,
    VPullToRefresh,
  },
  computed: {
    ...mapState(useAuthStore, {
      isAuthorized: (state) => state.isAuthorized,
      isBanner: (state) => state.isBanner,
      nonUsers: (state) => state.adminFlags.nonUsers,
    }),
    ...mapState(useBrowserStore, {
      librariesExist: (state) => state.page.librariesExist,
      showPlaceHolder(state) {
        return (
          this.nonUsers === undefined ||
          (this.isAuthorized &&
            (this.librariesExist == undefined || !state.browserPageLoaded))
        );
      },
      cards: (state) => [
        ...(state.page.groups ?? []),
        ...(state.page.books ?? []),
      ],
      numPages: (state) => state.page.numPages,
      query: (state) => state.settings.q,
      isSearchOpen: (state) => state.isSearchOpen,
      isSearchMode: (state) => state.isSearchMode,
    }),
    ...mapState(useSelectManyStore, {
      selectManyActive: (state) => state.active,
    }),
    browsePaneClasses() {
      const classes = {
        padFooter: this.numPages > 1,
      };
      let marginClass = "browsePane";
      if (this.selectManyActive) {
        marginClass += "SelectMany";
      }
      if (this.isSearchOpen) {
        marginClass += "Search";
      }
      if (this.isBanner) {
        marginClass += "Banner";
      }
      Reflect.set(classes, marginClass, true);
      return classes;
    },
    showBrowseItems() {
      return (
        this.cards &&
        this.cards.length > 0 &&
        this.isAuthorized &&
        !this.showPlaceHolder
      );
    },
    searchLimitMessage() {
      let res = "";
      if (!this.query) {
        return res;
      }
      const page = +this.$route.params.page;
      const limit = 100 * page;
      if (this.showPlaceHolder) {
        res += `Searching for ${limit} entries...`;
      } else if (this.numPages > page) {
        res += `Search results truncated to ${limit} entries.`;
        res += " Advance the page to look for more.";
      }
      return res;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["loadMtimes"]),
    async load({ done }) {
      await this.loadMtimes().then(done);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "../book-cover" as bookcover;

$top-toolbar-margin: 102px;
$card-margin: 32px;
$browse-pane-margin-top: calc($top-toolbar-margin + $card-margin);
$bottom-margin: 20px;
$select-many-height: 40px;

#browsePane {
  margin-left: max($card-margin, env(safe-area-inset-left));
  margin-right: max($card-margin, env(safe-area-inset-right));
  margin-bottom: max($card-margin, env(safe-area-inset-bottom));
  overflow: auto;
}

.browsePane {
  margin-top: $browse-pane-margin-top;
  overflow: hidden; // scroll is handled by the refresh container
}

.browsePaneSelectMany {
  margin-top: calc($browse-pane-margin-top + $select-many-height) !important;
}

.browsePaneSearch {
  margin-top: calc($browse-pane-margin-top + 32px) !important;
}

.browsePaneSelectManySearch {
  margin-top: calc(
    $browse-pane-margin-top + $select-many-height + 32px
  ) !important;
}

.browsePaneBanner {
  margin-top: calc(20px + $browse-pane-margin-top) !important;
}

.browsePaneSelectManyBanner {
  margin-top: calc(
    20px + $browse-pane-margin-top + $select-many-height
  ) !important;
}

.browsePaneSearchBanner {
  margin-top: calc(20px + $browse-pane-margin-top + 32px) !important;
}

.browsePaneSelectManySearchBanner {
  margin-top: calc(
    20px + $browse-pane-margin-top + $select-many-height + 32px
  ) !important;
}

#browsePaneRefreshContainer {
  height: calc(100vh - $top-toolbar-margin - $card-margin - $bottom-margin);
  overflow: auto;
  overscroll-behavior-y: contain;
}

#browsePaneRefreshContainer > :deep(.v-pull-to-refresh__scroll-container) {
  margin-top: $card-margin;
  display: grid;
  grid-template-columns: repeat(auto-fit, bookcover.$cover-width);
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

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  $small-card-margin: 16px;

  #browsePane {
    margin-left: max($small-card-margin, env(safe-area-inset-left));
    margin-right: max($small-card-margin, env(safe-area-inset-right));
    margin-bottom: max($small-card-margin, env(safe-area-inset-bottom));
  }

  #browsePaneRefreshContainer > :deep(.v-pull-to-refresh__scroll-container) {
    margin-top: $small-card-margin;
    grid-template-columns: repeat(auto-fit, bookcover.$small-cover-width);
    grid-gap: $small-card-margin;
    justify-content: space-evenly;
  }
}
</style>
