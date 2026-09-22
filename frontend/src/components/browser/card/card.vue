<template>
  <v-lazy :id="`card-${ids}`" transition="scale-transition">
    <div class="browserCardCoverWrapper" :class="readStateClass">
      <div class="browserCardTop">
        <BookCover
          :collection="item.collection"
          :pks="item.ids"
          :cover-pk="item.coverPk"
          :cover-custom-pk="item.coverCustomPk"
          :mtime="item.coverMtime ?? item.mtime"
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
      <!--
        Read state. ``aria-hidden`` because the state is already folded into
        the link's accessible name — one announcement per card, not two.
      -->
      <div class="readState" :title="readStateLabel" aria-hidden="true">
        <div class="readStateTrack">
          <div class="readStateFill" :style="readFillStyle" />
        </div>
      </div>
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
import {
  getReadFillPercent,
  getReadState,
  getReadStateLabel,
  READ_STATE,
} from "@/read-state";
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
    readState() {
      return getReadState(this.item);
    },
    readStateClass() {
      return `is-${this.readState}`;
    },
    readFillStyle() {
      const pct =
        this.readState === READ_STATE.UNREAD
          ? 0
          : getReadFillPercent(this.item);
      return { width: `${pct}%` };
    },
    readStateLabel() {
      return getReadStateLabel(this.item);
    },
    linkLabel() {
      /*
       * The read state is appended to every card, retiring the old progress
       * bar's ``${item.progress}% read`` label, which announced "0% read" on
       * every unread card and on every card that had been marked read without
       * being opened.
       *
       * Assembled from the non-empty parts because an untitled comic used to
       * produce a trailing space, and appending to that read ", unread".
       */
      const verb = this.item.collection === "comics" ? "Read" : "Browse to";
      const target = [verb, this.item.name].filter(Boolean).join(" ");
      return `${target}, ${this.readStateLabel}`;
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

/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
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
    border-color: rgb(var(--v-theme-primary));
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
    color: rgb(var(--v-theme-text-disabled));
    filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.8));
  }

  .selectManyCheckbox:hover :deep(.v-icon) {
    color: rgb(var(--v-theme-link-hover));
  }

  .selectManyCheckbox.checked :deep(.v-icon) {
    color: rgb(var(--v-theme-primary));
  }

  .selectManyCheckbox.checked:hover :deep(.v-icon) {
    color: rgb(var(--v-theme-link-hover));
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

  /*
   * READ STATE
   *
   * Lives in the 13px band between the cover box and the footer, never on
   * the artwork — which makes its backdrop a compile-time constant instead
   * of a per-cover gamble against ``object-fit: contain`` letterboxing, and
   * keeps the cover itself as clear of marks as it is today.
   *
   * A sibling of ``.browserCardTop``, so it sits outside both the
   * ``rgba(0, 0, 0, 0.55)`` hover scrim and the ``.cardCoverOverlay *``
   * hover reset that strips ``background-color`` from every descendant of
   * the router-link — no ``z-index`` needed. It also clears both 48x48
   * control buttons, so it needs no ``pointer-events: none`` and keeps its
   * native ``title`` tooltip.
   *
   * The slot is a fixed 10px with the track centered in it. If the track
   * grew from 3px to 6px in flow, a finished card's footer would sit lower
   * than its neighbour's and every grid row would get a ragged baseline.
   * 1 + 10 + 2 = 13, the band's previous height, so nothing reflows.
   */
  .readState {
    display: flex;
    align-items: center;
    width: 100%;
    height: 10px;
    margin-top: 1px;
  }

  /*
   * Painted only where there is a fill to measure against. An always-on
   * track under every unread cover reads as a ruled grid, and unread is the
   * majority state in most libraries.
   */
  .readStateTrack {
    width: 100%;
    height: 3px;
    border-radius: 2px;
    overflow: hidden;
    background-color: transparent;
    transition: height 0.15s;
  }

  .readStateFill {
    width: 0;
    height: 100%;
    border-radius: inherit;
    transition: width 0.15s;
  }

  .is-reading .readStateTrack,
  .is-finished .readStateTrack {
    background-color: rgba(var(--v-theme-text-disabled), 0.25);
  }

  /* Still reading: thin, orange. Orange means one thing on this card. */
  .is-reading .readStateFill {
    background-color: rgb(var(--v-theme-primary));
  }

  /*
   * Finished: double thickness. Thickness is the only boolean, so the fill
   * stays the real bookmark position — a comic marked read but never opened
   * is a bare 6px track, still unmistakable against an unread card's
   * nothing. Neutral grey keeps a second hue out of the grid.
   */
  .is-finished .readStateTrack {
    height: 6px;
    border-radius: 3px;
  }

  .is-finished .readStateFill {
    background-color: rgb(var(--v-theme-text-header));
  }

  .cardFooter {
    margin-top: 2px; /* the .readState slot is 10px tall */
    color: rgb(var(--v-theme-text-primary));
  }

  /*
   * The caption channel: luminance only, so it survives protanopia,
   * deuteranopia and achromatopsia intact, and it is the half of this design
   * that would port to table view for free. ``.displayName`` sets no colour
   * of its own so it inherits; the grey sublines in subtitle.vue set theirs
   * explicitly and are unaffected.
   */
  .is-finished .cardFooter {
    color: rgb(var(--v-theme-text-disabled));
  }

  @media (prefers-reduced-motion: reduce) {
    .readStateTrack,
    .readStateFill {
      transition: none;
    }
  }

  @media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
    .cardCoverOverlay {
      height: bookcover.$small-cover-height;
      width: bookcover.$small-cover-width;
    }
  }
}
</style>
