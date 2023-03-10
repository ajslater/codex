<template>
  <PagesScrollerVertical v-if="vertical" :book="book" />
  <PagesWindowHorizontal v-else :book="book" />
</template>

<script>
import { mapActions, mapState } from "pinia";

import PagesScrollerVertical from "@/components/reader/pages-scroller-vertical.vue";
import PagesWindowHorizontal from "@/components/reader/pages-window-horizontal.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesView",
  components: {
    PagesWindowHorizontal,
    PagesScrollerVertical,
  },
  props: {
    book: { type: Object, required: true },
  },
  emits: ["click"],
  computed: {
    ...mapState(useReaderStore, {
      storePk: (state) => state.pk,
    }),
    settings() {
      return this.getSettings(this.book);
    },
    vertical() {
      return this.settings.vertical;
    },
  },
  watch: {
    $route(to) {
      if (+to.params.pk === this.book.pk) {
        this.setActivePage(+to.params.page, true);
      }
    },
  },
  created() {
    if (this.book.pk === this.storePk) {
      // Active Book
      this.setActivePage(+this.$route.params.page);
    }
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "setActivePage"]),
  },
};
</script>

/* Inherits v-window styles from books-window */
