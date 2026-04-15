<template>
  <v-lazy :id="`card-${ids}`" transition="scale-transition">
    <div class="browserCardCoverWrapper">
      <div class="browserCardTop">
        <BookCover
          :group="item.group"
          :pks="item.ids"
          :mtime="item.mtime"
          :child-count="item.childCount"
        />
        <div
          v-if="selectManyActive"
          class="cardCoverOverlay selectManyOverlay"
          :class="{ selected: checked }"
          :aria-label="linkLabel"
          @click="toggleItem(item)"
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
          @click.stop.prevent="toggleItem(item)"
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
import { getReaderRoute } from "@/route";
import { useBrowserStore } from "@/stores/browser";
import { useBrowserSelectManyStore } from "@/stores/browser-select-many";

const SCROLL_DELAY = 100;
const HEADER_OFFSET = -170;

export default {
  name: "BrowserCard",
  components: {
    BookCover,
    BrowserCardControls,
    BrowserCardSubtitle,
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
    checked() {
      return this.isSelected(this.item);
    },
    linkLabel() {
      let label = "";
      label += this.item.group === "c" ? "Read" : "Browse to";
      label += " " + this.item.name;
      return label;
    },
    ids() {
      return this.item.ids.join(",");
    },
    browserRoute() {
      return {
        name: "browser",
        params: {
          group: this.item.group,
          pks: this.ids,
          page: 1,
        },
        query: { ts: this.item.mtime },
      };
    },
    toRoute() {
      return this.item.group === "c"
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
  methods: {
    ...mapActions(useSelectManyStore, ["toggleItem"]),
    scrollToMe: function () {
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
      setTimeout(
        function () {
          // This works while nextTick() does not.
          el.scrollIntoView();
          /*
           * Adjust for toolbars
           * For some reason with vue3 i need another delay.
           */
          setTimeout(function () {
            window.scrollBy(0, HEADER_OFFSET);
          }, SCROLL_DELAY);
        },
        // A little hacky delay makes it work even more frequently.
        SCROLL_DELAY,
      );
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
