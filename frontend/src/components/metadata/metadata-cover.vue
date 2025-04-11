<template>
  <div class="bookCoverWrapper">
    <BookCover
      id="bookCover"
      :group="group"
      :pks="md.ids"
      :child-count="md.childCount"
      :finished="md.finished"
      :mtime="md.mtime"
    />
    <v-progress-linear
      class="bookCoverProgress"
      :model-value="md.progress"
      rounded
      background-color="inherit"
      height="2"
      aria-label="% read"
    />
  </div>
</template>
<script>
import { mapState } from "pinia";

import BookCover from "@/components/book-cover.vue";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBookCover",
  components: {
    BookCover,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
  },
};
</script>
<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.bookCoverWrapper {
  position: relative;
  width: 165px;
}

#bookCover {
  padding-top: 0px !important;
}

.bookCoverProgress {
  margin-top: -11px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .bookCoverWrapper {
    width: 100px;
  }

  .bookCoverProgress {
    margin-top: 1px;
  }
}
</style>
