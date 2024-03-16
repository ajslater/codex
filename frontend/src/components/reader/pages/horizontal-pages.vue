<template>
  <ScaleForScroll class="noWrap">
    <BookPage
      v-if="showPageOne"
      ref="pageOne"
      :book="book"
      :page="pageOne"
      class="horizontalPage"
    />
    <BookPage
      v-if="showPageTwo"
      :book="book"
      :page="pageTwo"
      class="horizontalPage"
    />
  </ScaleForScroll>
</template>

<script>
import { mapActions, mapGetters } from "pinia";

import BookPage from "@/components/reader/pages/page/page.vue";
import ScaleForScroll from "@/components/reader/pages/scale-for-scroll.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "HorizontalPages",
  components: { BookPage, ScaleForScroll },
  props: {
    book: { type: Object, required: true },
    page: { type: Number, required: true },
  },
  emits: ["click"],
  computed: {
    ...mapGetters(useReaderStore, ["isOnCoverPage", "isReadInReverse"]),
    showSecondPage() {
      // TODO isOnCoverPage should be book specific not from store.
      const settings = this.getSettings(this.book);
      return (
        settings.twoPages &&
        !this.isOnCoverPage &&
        this.page < this.book.maxPage
      );
    },
    showPageOne() {
      return !this.isReadInReverse || this.showSecondPage;
    },
    showPageTwo() {
      return this.isReadInReverse || this.showSecondPage;
    },
    pageOne() {
      return this.isReadInReverse ? this.page + 1 : this.page;
    },
    pageTwo() {
      return this.isReadInReverse ? this.page : this.page + 1;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["getSettings"]),
  },
};
</script>

<style scoped lang="scss">
.noWrap {
  white-space: nowrap;
}

.horizontalPage {
  display: inline-block;
}
</style>
