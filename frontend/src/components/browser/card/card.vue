<template>
  <v-lazy
    :id="`card-${item.pk}`"
    transition="scale-transition"
    class="browserTile"
  >
    <div class="browserCardCoverWrapper" @click="doubleTapHovered = true">
      <BookCover
        :cover-pk="item.coverPk"
        :group="item.group"
        :child-count="item.childCount"
        :finished="item.finished"
      />
      <router-link
        v-if="toRoute"
        class="cardCoverOverlay"
        :to="toRoute"
        :aria-label="linkLabel"
      >
        <BrowserCardControls :item="item" :eye-open="true" />
      </router-link>
      <div v-else class="cardCoverOverlay">
        <BrowserCardControls :item="item" :eye-open="false" />
      </div>
      <v-progress-linear
        class="bookCoverProgress"
        :background-color="progressBackgroundColor"
        :model-value="item.progress"
        aria-label="% read"
        rounded
        height="2"
      />
      <BrowserCardSubtitle :item="item" />
    </div>
  </v-lazy>
</template>

<script>
import BookCover from "@/components/book-cover.vue";
import BrowserCardControls from "@/components/browser/card/controls.vue";
import BrowserCardSubtitle from "@/components/browser/card/subtitle.vue";
import { IS_IOS, IS_TOUCH } from "@/platform";
import { getReaderRoute } from "@/route";

const HEADER_OFFSET = (96 + 16) * -1;

export default {
  name: "BrowserCard",
  components: {
    BookCover,
    BrowserCardControls,
    BrowserCardSubtitle,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      doubleTapHovered: !IS_TOUCH || IS_IOS,
    };
  },
  // Stored here instead of data to be non-reactive
  computed: {
    linkLabel: function () {
      let label = "";
      label += this.item.group === "c" ? "Read" : "Browse to";
      label += " " + this.item.headerName;
      return label;
    },
    toRoute: function () {
      if (!this.doubleTapHovered) {
        return {};
      }
      return this.item.group === "c"
        ? getReaderRoute(this.item)
        : {
            name: "browser",
            params: { group: this.item.group, pk: this.item.pk, page: 1 },
          };
    },
    progressBackgroundColor: function () {
      return this.item.progress
        ? this.$vuetify.theme.current.colors.row
        : "inherit";
    },
  },
  mounted() {
    this.scrollToMe();
  },
  methods: {
    scrollToMe: function () {
      if (
        !this.$route.hash ||
        this.$route.hash.split("-")[1] !== String(this.item.pk)
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
          // Adjust for toolbars
          window.scrollBy(0, HEADER_OFFSET);
        },
        // A little hacky delay makes it work even more frequently.
        100
      );
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@import "../../book-cover.scss";
.browserCardCoverWrapper {
  position: relative;
}
.cardCoverOverlay {
  position: absolute;
  top: 0px;
  left: 0px;
  height: $cover-height;
  width: $cover-width;
  border-radius: 5px;
  border: solid thin transparent;
}

.browserCardCoverWrapper:hover > .cardCoverOverlay {
  background-color: rgba(var(--v-theme-bookCoverOverlayHover), 0.55);
  border: solid thin;
  border-color: rbg(var(--v-theme-primary));
}
.browserCardCoverWrapper:hover > .cardCoverOverlay * {
  opacity: 1;
}
.bookCoverProgress {
  margin-top: 1px;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .cardCoverOverlay {
    height: $small-cover-height;
    width: $small-cover-width;
  }
}
</style>
