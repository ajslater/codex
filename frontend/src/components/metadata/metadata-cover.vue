<template>
  <div class="bookCoverWrapper">
    <v-img
      v-if="forceGenericCover"
      :src="genericCoverSrc"
      class="genericCoverImg"
    />
    <BookCover
      v-else
      id="bookCover"
      :group="group"
      :pks="md.ids"
      :cover-pk="md.coverPk"
      :cover-custom-pk="md.coverCustomPk"
      :child-count="md.childCount"
      :mtime="md.mtime"
    />
    <v-progress-linear
      v-if="!forceGenericCover"
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

import { getPlaceholderSrc } from "@/api/v3/browser";
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
    forceGenericCover: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    genericCoverSrc() {
      return getPlaceholderSrc(this.group);
    },
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

.genericCoverImg {
  width: 165px;
  opacity: 0.6;
}

.bookCoverProgress {
  margin-top: -11px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .bookCoverWrapper {
    width: 100px;
  }

  .genericCoverImg {
    width: 100px;
  }

  .bookCoverProgress {
    margin-top: 1px;
  }
}
</style>
