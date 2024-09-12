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
import { mapActions } from "pinia";

import BookPage from "@/components/reader/pager/page/page.vue";
import ScaleForScroll from "@/components/reader/pager/scale-for-scroll.vue";
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
    bookSettings() {
      return this.getBookSettings(this.book);
    },
    isReadInReverse() {
      return this.bookSettings.isReadInReverse;
    },
    showSecondPage() {
      return (
        this.bookSettings.twoPages &&
        this.page < this.book.maxPage &&
        !this.isCoverPage(this.book, this.page)
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
    ...mapActions(useReaderStore, ["getBookSettings", "isCoverPage"]),
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
