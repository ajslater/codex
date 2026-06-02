<template>
  <v-lazy :id="`card-${ids}`" transition="scale-transition">
    <div class="browserCardCoverWrapper">
      <div class="browserCardTop">
        <BookCover
          :collection="item.collection"
          :pks="item.ids"
          :cover-pk="item.coverPk"
          :cover-custom-pk="item.coverCustomPk"
          :mtime="item.mtime"
          :child-count="item.childCount"
        />
        <div
          v-if="selectManyActive"
          class="cardCoverOverlay selectManyOverlay"
          :class="{ selected: checked }"
          :aria-label="linkLabel"
          @click="selectItemAt(item, { shift: $event.shiftKey })"
        />
        <router-link
          v-else
          class="cardCoverOverlay"
          :to="toRoute"
          :aria-label="linkLabel"
        >
          <BrowserCardControls :item="item" :eye-open="Boolean(toRoute)" />
        </router-link>
        <v-checkbox-btn
          class="selectManyCheckbox"
          :class="{ checked }"
          density="compact"
          :model-value="checked"
          @click.stop.prevent="selectItemAt(item, { shift: $event.shiftKey })"
        />
        <FavoriteToggle
          v-if="favoritePk"
          class="cardFavoriteToggle"
          :class="{ favoriteVisible: isFavoriteCard }"
          :collection="item.collection"
          :pk="favoritePk"
        />
      </div>
      <v-progress-linear
        class="bookCoverProgress"
        :bg-opacity="progressBGOpacity"
        :model-value="item.progress"
        :aria-label="`${item.progress}% read`"
        rounded
        height="2"
      />
      <footer class="cardFooter">
        <BrowserCardSubtitle :item="item" />
        <OrderByCaption :item="item" />
      </footer>
    </div>
  </v-lazy>
</template>

<script>
import { mapActions, mapState } from "pinia";

import BookCover from "@/components/book-cover.vue";
import BrowserCardControls from "@/components/browser/card/controls.vue";
import OrderByCaption from "@/components/browser/card/order-by-caption.vue";
import BrowserCardSubtitle from "@/components/browser/card/subtitle.vue";
import FavoriteToggle from "@/components/favorite-toggle.vue";
import { getReaderRoute, routeForCollection } from "@/route";
import { useBrowserStore } from "@/stores/browser";
import { useBrowserSelectManyStore } from "@/stores/browser-select-many";
import { useFavoritesStore } from "@/stores/favorites";

const SCROLL_DELAY = 100;

export default {
  name: "BrowserCard",
  components: {
    BookCover,
    BrowserCardControls,
    BrowserCardSubtitle,
    FavoriteToggle,
    OrderByCaption,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  // Stored here instead of data to be non-reactive
  computed: {
    ...mapState(useBrowserStore, {
      importMetadata: (state) => state.page.adminFlags.importMetadata,
    }),
    ...mapState(useBrowserSelectManyStore, {
      selectManyActive: (state) => state.active,
      isSelected: (state) => state.isSelected,
    }),
    ...mapState(useFavoritesStore, ["isFavorite"]),
    checked() {
      return this.isSelected(this.item);
    },
    favoritePk() {
      /*
       * The toggle drives a single backend row. Cards that aggregate
       * multiple ids (folder rollups, story-arc cross-publisher
       * cards) can't be favorited atomically — hide the star
       * rather than guess which pk to write.
       */
      const ids = this.item?.ids;
      if (!Array.isArray(ids) || ids.length !== 1) return undefined;
      return ids[0];
    },
    isFavoriteCard() {
      return Boolean(
        this.favoritePk &&
        this.isFavorite(this.item.collection, this.favoritePk),
      );
    },
    linkLabel() {
      let label = "";
      label += this.item.collection === "comics" ? "Read" : "Browse to";
      label += " " + this.item.name;
      return label;
    },
    ids() {
      return this.item.ids.join(",");
    },
    browserRoute() {
      const { collection, parentIds } = routeForCollection({
        collection: this.item.collection,
        pks: this.ids,
      });
      return {
        name: "browser",
        params: parentIds.length
          ? { collection, parentIds: parentIds.join(",") }
          : { collection },
        query: { ts: this.item.mtime },
      };
    },
    toRoute() {
      return this.item.collection === "comics"
        ? getReaderRoute(this.item, this.importMetadata)
        : this.browserRoute;
    },
    progressBGOpacity() {
      return this.item.progress ? 0.1 : 0;
    },
  },
  mounted() {
    this.scrollToMe();
  },
  beforeUnmount() {
    /*
     * Cancel any pending scroll-restore timer so a card that
     * unmounts during the 100ms layout window (rapid filter
     * change, live-reload, route transition) doesn't fire
     * ``scrollIntoView`` on a detached node.
     */
    if (this._scrollTimer) {
      globalThis.clearTimeout(this._scrollTimer);
      this._scrollTimer = 0;
    }
  },
  methods: {
    ...mapActions(useBrowserSelectManyStore, ["selectItemAt"]),
    scrollToMe() {
      if (
        !this.$route.hash ||
        this.$route.hash.split("-")[1] !== String(this.ids)
      ) {
        return;
      }
      const el = this.$el;
      if (!el) {
        console.warn("No element found to scroll to!");
        return;
      }
      /*
       * Wait one layout pass before scrolling. The empirical
       * 100ms delay was tuned against Vue 3's mount timing and
       * ``nextTick`` doesn't reliably substitute. Track the id
       * so ``beforeUnmount`` can cancel it.
       */
      this._scrollTimer = globalThis.setTimeout(() => {
        this._scrollTimer = 0;
        el.scrollIntoView();
      }, SCROLL_DELAY);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "../../book-cover" as bookcover;

.browserCardCoverWrapper {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cardCoverOverlay {
  position: absolute;
  top: 0px;
  left: 0px;
  height: bookcover.$cover-height;
  width: bookcover.$cover-width;
  border-radius: 5px;
  border: solid thin transparent;
}

.browserCardCoverWrapper:hover > .browserCardTop > .cardCoverOverlay {
  background-color: rgba(0, 0, 0, 0.55);
  border: solid thin;
  border-color: rbg(var(--v-theme-primary));
}

.browserCardCoverWrapper:hover > .browserCardTop > .cardCoverOverlay * {
  background-color: transparent;
  opacity: 1;
}

/* Select Many Overlay */
.selectManyOverlay {
  cursor: pointer;
}

.selectManyOverlay.selected {
  border: solid 2px rgb(var(--v-theme-primary)) !important;
  background-color: rgba(var(--v-theme-primary), 0.15);
}

/* Checkbox: top left, always present, shown on hover or when checked */
.selectManyCheckbox {
  position: absolute !important;
  top: 2px;
  left: 2px;
  z-index: 2;
  opacity: 0;
  transition: opacity 0.15s;
}

.selectManyCheckbox.checked {
  opacity: 1;
}

.browserCardCoverWrapper:hover > .browserCardTop > .selectManyCheckbox {
  opacity: 1;
}

.selectManyCheckbox :deep(.v-selection-control) {
  min-height: auto;
}

.selectManyCheckbox :deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
  filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.8));
}

.selectManyCheckbox:hover :deep(.v-icon) {
  color: rgb(var(--v-theme-linkHover));
}

.selectManyCheckbox.checked :deep(.v-icon) {
  color: rgb(var(--v-theme-primary));
}

.selectManyCheckbox.checked:hover :deep(.v-icon) {
  color: rgb(var(--v-theme-linkHover));
}

/*
 * Favorite star sits in the top-right of the cover, stacked just
 * below the childCount badge (also top-right) so the count circle
 * stays unobscured. Hidden by default so it doesn't compete with
 * the cover art; surfaces on card hover for discovery, and stays
 * lit (full opacity) when the row is favorited so the user can
 * scan a page for their starred items.
 *
 * Sibling of ``.cardCoverOverlay`` — outside the router-link's
 * opacity-fade subtree, so the lit state is unaffected by the
 * controls' ``opacity: 0`` baseline.
 */
.cardFavoriteToggle {
  position: absolute !important;
  top: 1.75rem; // clears the ~1.5rem-tall ``.childCount`` badge
  right: 0px;
  z-index: 2;
  opacity: 0;
  transition: opacity 0.15s;
}

.browserCardCoverWrapper:hover > .browserCardTop > .cardFavoriteToggle {
  opacity: 1;
}

.cardFavoriteToggle.favoriteVisible {
  opacity: 1;
}

.bookCoverProgress {
  margin-top: 1px;
}

.cardFooter {
  margin-top: 10px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .cardCoverOverlay {
    height: bookcover.$small-cover-height;
    width: bookcover.$small-cover-width;
  }
}
</style>
