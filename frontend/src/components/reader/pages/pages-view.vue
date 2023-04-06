<template>
  <PagesVerticalScroller v-if="vertical" :book="book" @click="$emit['click']" />
  <PagesHorizontalWindow v-else :book="book" @click="$emit['click']" />
</template>

<script>
import { mapActions, mapState } from "pinia";

import PagesHorizontalWindow from "@/components/reader/pages/horizontal-window.vue";
import PagesVerticalScroller from "@/components/reader/pages/vertical-scroller.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "PagesView",
  components: {
    PagesHorizontalWindow,
    PagesVerticalScroller,
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
      this.setActivePage(+this.$route.params.page, true);
    }
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings", "setActivePage"]),
  },
};
</script>

/* Inherits v-window styles from books-window */
