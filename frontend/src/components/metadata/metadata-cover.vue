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
      :collection="collection"
      :pks="md.ids"
      :cover-pk="md.coverPk"
      :cover-custom-pk="md.coverCustomPk"
      :child-count="md.childCount"
      :mtime="md.mtime"
    />
    <ReadStateBar
      v-if="!forceGenericCover"
      class="metadataReadState"
      :item="md"
      :aria-label="readStateLabel"
    />
  </div>
</template>
<script>
import { mapState } from "pinia";

import { getPlaceholderSrc } from "@/api/v4/browser";
import BookCover from "@/components/book-cover.vue";
import ReadStateBar from "@/components/read-state-bar.vue";
import { getReadStateLabel } from "@/read-state";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBookCover",
  components: {
    BookCover,
    ReadStateBar,
  },
  props: {
    collection: {
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
      return getPlaceholderSrc(this.collection);
    },
    readStateLabel() {
      return getReadStateLabel(this.md);
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

/*
 * The negative margins keep the read state's 10px slot centered where the
 * old 2px bar sat.
 */
.metadataReadState {
  margin-top: -15px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .bookCoverWrapper {
    width: 100px;
  }

  .genericCoverImg {
    width: 100px;
  }

  .metadataReadState {
    margin-top: -3px;
  }
}
</style>
