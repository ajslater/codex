<template>
  <div
    v-if="show"
    class="bookChangeColumn"
    :class="{ [direction]: true }"
    @click.stop="setBookChangeFlag(direction)"
  >
    <v-navigation-drawer
      v-model="isDrawerOpen"
      :class="{ bookChangeDrawer: true, [direction]: true }"
      disable-resize-watcher
      disable-route-watcher
      :location="direction === 'prev' ? 'left' : 'right'"
      temporarary
      touchless
    >
      <router-link
        class="navLink"
        :to="route"
        :aria-label="label"
        :title="label"
        @click="$event.stopImmediatePropagation()"
      >
        <v-icon class="bookChangeIcon"> {{ icon }} </v-icon>
      </router-link>
    </v-navigation-drawer>
  </div>
</template>
<script>
import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { linksInfo } from "@/components/reader/prefetch-links";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "BookChangeDrawer",
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  head() {
    return linksInfo([this.prefetchSrc1, this.prefetchSrc2]);
  },
  computed: {
    ...mapState(useReaderStore, {
      show(state) {
        if (this.direction === "prev") {
          return +this.$route.params.page === 0;
        }
        // next
        const maxPage = state.activeBook ? state.activeBook.maxPage : 0;
        const adj = state.activeSettings.twoPages ? 1 : 0;
        const limit = maxPage + adj;
        return +this.$route.params.page >= limit;
      },
      prefetchSrc2(state) {
        const book = state.books.get(this.params.pk);
        const bookSettings = book ? book.settings || {} : {};
        const otherBookSettings = this.getSettings(
          state.readerSettings,
          bookSettings
        );
        if (!this.isDrawerOpen || !this.params || !otherBookSettings.twoPages) {
          return false;
        }
        const params = { pk: this.params.pk, page: this.params.page + 1 };
        return getComicPageSource(params);
      },
      isDrawerOpen(state) {
        return state.bookChange === this.direction;
      },
      params(state) {
        return state.routes.books[this.direction];
      },
      icon() {
        return this.direction === "next" ? mdiBookArrowDown : mdiBookArrowUp;
      },
    }),
    prefetchSrc1() {
      if (!this.isDrawerOpen || !this.params) {
        return false;
      }
      return getComicPageSource(this.params);
    },
    route() {
      return this.params ? { params: this.params } : {};
    },
    label() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return `${prefix} Book`;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "setBookChangeFlag"]),
  },
};
</script>
<style scoped lang="scss">
.bookChangeColumn {
  position: fixed;
  height: 100%;
  width: 33vw;
}
.prev {
  cursor: n-resize;
  left: 0px;
}
.next {
  cursor: s-resize;
  right: 0px;
}
.navLink {
  display: block;
  height: 100%;
}
$iconSize: 25%;
.bookChangeIcon {
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
  height: $iconSize;
  width: $iconSize;
  color: white;
}
:deep(.bookChangeDrawer) {
  width: 33vw !important;
  opacity: 0.75 !important;
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.v-main {
  /* Hack for using v-navigation drawer inside v-app */
  --v-layout-left: 0px !important;
  --v-layout-right: 0px !important;
}
</style>
