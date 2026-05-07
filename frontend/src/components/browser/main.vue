<template>
  <div id="browsePane" :class="browsePaneClasses">
    <BrowserTable v-if="isTableMode && showBrowseItems" />
    <v-pull-to-refresh
      v-else-if="showBrowseItems"
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
    <template v-else-if="showPlaceHolder">
      <PlaceholderLoading class="placeholder" />
      <button
        v-if="showCancelButton"
        class="cancelLoadingButton"
        :title="cancelButtonTitle"
        @click="onCancelLoading"
      >
        Cancel
      </button>
    </template>
    <BrowserEmptyState v-else />
    <div
      v-if="searchLimitMessage"
      id="searchLimitMessage"
      title="You may change this in the settings drawer"
    >
      {{ searchLimitMessage }}
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BrowserCard from "@/components/browser/card/card.vue";
import BrowserEmptyState from "@/components/browser/empty.vue";
import BrowserTable from "@/components/browser/table/browser-table.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useBrowserSelectManyStore } from "@/stores/browser-select-many";
import { VPullToRefresh } from "vuetify/labs/VPullToRefresh";

const CANCEL_TIMEOUT = 5_000;

export default {
  name: "BrowserMain",
  components: {
    BrowserCard,
    BrowserEmptyState,
    BrowserTable,
    PlaceholderLoading,
    VPullToRefresh,
  },
  data() {
    return {
      /*
       * 10s grace period before the cancel button surfaces on the
       * spinner. Backend table-view queries can take a long time on
       * large libraries; cancelling lets the user back out and keep
       * the previous results showing instead of waiting forever.
       */
      cancelButtonTimerHandle: null,
      cancelButtonReady: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isAuthorized: (state) => state.isAuthorized,
      isBanner: (state) => state.isBanner,
      nonUsers: (state) => state.adminFlags.nonUsers,
    }),
    ...mapState(useBrowserStore, {
      librariesExist: (state) => state.page.librariesExist,
      pageMtime: (state) => state.page.mtime,
      showPlaceHolder(state) {
        return (
          this.nonUsers === undefined ||
          (this.isAuthorized &&
            (this.librariesExist == undefined || !state.browserPageLoaded))
        );
      },
      showCancelButton(state) {
        /*
         * Visible only when (a) the spinner has been showing for
         * the grace period, AND (b) there's actually a prior page
         * to fall back to. On a brand-new session ``page.mtime`` is
         * ``0`` so cancelling would just leave a blank screen — no
         * use to the user, so the button stays hidden in that case.
         */
        return (
          this.cancelButtonReady && this.showPlaceHolder && state.page.mtime > 0
        );
      },
      cards(state) {
        /*
         * Skip the spread when one of the lists is empty. The
         * typical browser page is either all groups (publishers,
         * series, volumes) or all books — never a mix — so the
         * common case is "spread an array against an empty
         * array", which still allocates a fresh wrapper per
         * render even though the contents are identical to the
         * non-empty input. Returning the reference directly when
         * we can lets Vue's diff cache shortcut to "same array,
         * same items" and the v-for stays stable across renders.
         */
        const groups = state.page.groups;
        const books = state.page.books;
        if (!groups || groups.length === 0) return books ?? [];
        if (!books || books.length === 0) return groups;
        return [...groups, ...books];
      },
      tableModeRequested: (state) => state.settings.viewMode === "table",
      tableRowCount: (state) =>
        Array.isArray(state.page.rows) ? state.page.rows.length : 0,
      numPages: (state) => state.page.numPages,
      search: (state) => state.settings.search,
      isSearchOpen: (state) => state.isSearchOpen,
      isSearchMode: (state) => state.isSearchMode,
    }),
    ...mapState(useBrowserSelectManyStore, {
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
    isTableMode() {
      /*
       * The user's persisted preference is honored only on viewports
       * wide enough to actually use the table. Below ~960px (Vuetify
       * smAndDown) we auto-fall-back to the cover grid since a multi-
       * column table is unusable on phone-sized screens. The setting
       * itself isn't changed — flip the device into landscape / wider
       * and the table reappears.
       */
      return this.tableModeRequested && !this.$vuetify.display.smAndDown;
    },
    cancelButtonTitle() {
      /*
       * Hover tooltip on the cancel button. Reflects what the
       * cancel will actually reset: in cover view only the order
       * key changes; in table view the column set is also rolled
       * back to the registry defaults for the current top-group.
       */
      return this.isTableMode ? "Reset order and columns" : "Reset order";
    },
    showBrowseItems() {
      if (!this.isAuthorized || this.showPlaceHolder) return false;
      if (this.isTableMode) {
        return this.tableRowCount > 0;
      }
      return this.cards && this.cards.length > 0;
    },
    searchLimitMessage() {
      let res = "";
      if (!this.search) {
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
  watch: {
    showPlaceHolder: {
      immediate: true,
      handler(visible) {
        /*
         * Spinner just appeared: arm the 10s timer that surfaces
         * the cancel button. Spinner hid: clear the timer and
         * reset visibility so the next request gets its own grace.
         */
        if (this.cancelButtonTimerHandle) {
          globalThis.clearTimeout(this.cancelButtonTimerHandle);
          this.cancelButtonTimerHandle = null;
        }
        if (visible) {
          this.cancelButtonTimerHandle = globalThis.setTimeout(() => {
            this.cancelButtonReady = true;
            this.cancelButtonTimerHandle = null;
          }, CANCEL_TIMEOUT);
        } else {
          this.cancelButtonReady = false;
        }
      },
    },
  },
  beforeUnmount() {
    if (this.cancelButtonTimerHandle) {
      globalThis.clearTimeout(this.cancelButtonTimerHandle);
      this.cancelButtonTimerHandle = null;
    }
  },
  methods: {
    ...mapActions(useBrowserStore, ["cancelBrowserPage", "loadMtimes"]),
    async load({ done }) {
      await this.loadMtimes().then(done);
    },
    onCancelLoading() {
      /*
       * ``cancelBrowserPage`` is async — it aborts the in-flight
       * request, resets settings to defaults, and re-fetches.
       * Fire-and-forget here since the spinner state is driven
       * by the store, not by this handler's return value.
       */
      this.cancelBrowserPage();
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
$browse-pane-padding-top: calc($top-toolbar-margin + $card-margin);
$select-many-height: 40px;
$search-toolbar-height: 32px;
$banner-height: 20px;

// Single scroller: #browsePane fills the viewport exactly so its content
// area is a known size, and #browsePaneRefreshContainer fills that area.
// The refresh container is the only element with overflow: auto.
//
// Side padding lives on the refresh container (not on #browsePane) so the
// scrollbar sits at the viewport edge instead of inset by $card-margin.
#browsePane {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  box-sizing: border-box;
  padding-top: $browse-pane-padding-top;
  padding-bottom: max($card-margin, env(safe-area-inset-bottom));
  overflow: hidden;
}

.browsePaneSelectMany {
  padding-top: calc($browse-pane-padding-top + $select-many-height) !important;
}

.browsePaneSearch {
  padding-top: calc(
    $browse-pane-padding-top + $search-toolbar-height
  ) !important;
}

.browsePaneSelectManySearch {
  padding-top: calc(
    $browse-pane-padding-top + $select-many-height + $search-toolbar-height
  ) !important;
}

.browsePaneBanner {
  padding-top: calc($banner-height + $browse-pane-padding-top) !important;
}

.browsePaneSelectManyBanner {
  padding-top: calc(
    $banner-height + $browse-pane-padding-top + $select-many-height
  ) !important;
}

.browsePaneSearchBanner {
  padding-top: calc(
    $banner-height + $browse-pane-padding-top + $search-toolbar-height
  ) !important;
}

.browsePaneSelectManySearchBanner {
  padding-top: calc(
    $banner-height + $browse-pane-padding-top + $select-many-height +
      $search-toolbar-height
  ) !important;
}

#browsePaneRefreshContainer {
  flex: 1;
  min-height: 0;
  padding-left: max($card-margin, env(safe-area-inset-left));
  padding-right: max($card-margin, env(safe-area-inset-right));
  overflow-x: clip; // prevents horizontal scrollbar on Firefox
  overflow-y: auto;
  overscroll-behavior-y: contain;
}

#browsePaneRefreshContainer > :deep(.v-pull-to-refresh__scroll-container) {
  display: grid;
  grid-template-columns: repeat(auto-fit, bookcover.$cover-width);
  grid-gap: $card-margin;
  align-content: flex-start;
}

// Reserve room at the bottom of the scroll content for the fixed
// pagination toolbar so the last cards aren't hidden behind it.
.padFooter > #browsePaneRefreshContainer {
  padding-bottom: 45px;
}

.placeholder {
  position: fixed;
  height: 50vh !important;
  width: 50vw !important;
  top: calc(50% + 75px);
  left: 50%;
  transform: translate(-50%, -50%);
}

/*
 * Cancel button surfaced after a 10s grace period on a slow
 * browser query. Sits centered below the spinner so the user can
 * abandon the in-flight request and keep the previous results.
 * Plain ``<button>`` instead of ``<v-btn>`` keeps the visual
 * weight low — the spinner is the focal point; the cancel is a
 * subtle escape hatch.
 */
.cancelLoadingButton {
  position: fixed;
  top: calc(50% + 75px);
  left: 50%;
  transform: translate(-50%, calc(-50% + 30vh));
  padding: 6px 18px;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textPrimary));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  z-index: 10;
}

.cancelLoadingButton:hover {
  color: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
}

#searchLimitMessage {
  flex-shrink: 0;
  padding-top: 20px;
  text-align: center;
  font-size: 14px;
  color: rgb(var(--v-theme-textDisabled));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  $small-card-margin: 16px;

  #browsePane {
    padding-bottom: max($small-card-margin, env(safe-area-inset-bottom));
  }

  #browsePaneRefreshContainer {
    padding-left: max($small-card-margin, env(safe-area-inset-left));
    padding-right: max($small-card-margin, env(safe-area-inset-right));
  }

  #browsePaneRefreshContainer > :deep(.v-pull-to-refresh__scroll-container) {
    grid-template-columns: repeat(auto-fit, bookcover.$small-cover-width);
    grid-gap: $small-card-margin;
    justify-content: space-evenly;
  }
}
</style>
