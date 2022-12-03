<template>
  <v-navigation-drawer
    class="changeBookDrawer"
    :class="classes"
    absolute
    :left="direction === 'prev'"
    :right="direction === 'next'"
    temporarary
    :model-value="isDrawerOpen"
    width="33%"
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
</template>
<script>
import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import { useReaderStore } from "@/stores/reader";

const PREFETCH_LINK = { rel: "prefetch", as: "image" };

export default {
  name: "ChangeBookDrawer",
  props: {
    direction: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      icon: this.direction === "next" ? mdiBookArrowDown : mdiBookArrowUp,
      classes: { [this.direction]: true },
    };
  },
  head() {
    const links = [];
    if (this.prefetchSrc1) {
      links.push({ ...PREFETCH_LINK, href: this.prefetchSrc1 });
    }
    if (this.prefetchSrc2) {
      links.push({ ...PREFETCH_LINK, href: this.prefetchSrc2 });
    }
    if (links.length > 0) {
      return { link: links };
    }
  },
  computed: {
    ...mapState(useReaderStore, {
      isDrawerOpen(state) {
        return state.bookChange === this.direction;
      },
      params(state) {
        return state.routes.books[this.direction];
      },
      prefetchSrc1(state) {
        if (!this.isDrawerOpen || !this.params) {
          return false;
        }
        return getComicPageSource(this.params, state.timestamp);
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
        return getComicPageSource(params, state.timestamp);
      },
    }),
    route() {
      return this.params ? { params: this.params } : {};
    },
    label() {
      const prefix = this.direction === "prev" ? "Previous" : "Next";
      return `${prefix} Book`;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings"]),
  },
};
</script>
<style scoped lang="scss">
.changeBookDrawer {
  position: fixed;
  height: 100vh;
  opacity: 0.75;
  z-index: 15;
}
.prev {
  cursor: n-resize;
}
.next {
  cursor: s-resize;
}
.navLink {
  display: block;
  height: 100%;
}
.bookChangeIcon {
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
$iconSize: 96px;
.bookChangeIcon svg {
  height: $iconSize !important;
  width: $iconSize !important;
  font-size: $iconSize !important;
}
</style>
