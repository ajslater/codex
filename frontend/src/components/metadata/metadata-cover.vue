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
    <div
      v-if="!forceGenericCover"
      class="readState"
      :class="readStateClass"
      :aria-label="readStateLabel"
    >
      <div class="readStateTrack">
        <div class="readStateFill" :style="readFillStyle" />
      </div>
    </div>
  </div>
</template>
<script>
import { mapState } from "pinia";

import { getPlaceholderSrc } from "@/api/v4/browser";
import BookCover from "@/components/book-cover.vue";
import {
  getReadFillPercent,
  getReadState,
  getReadStateLabel,
  READ_STATE,
} from "@/read-state";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBookCover",
  components: {
    BookCover,
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
    /*
     * Same derivation as the browser card, from the shared module — the two
     * surfaces show the same comic at the same time and must not disagree.
     * Unlike the card this is never gated by the browser setting: the dialog
     * is where the user came to read the details.
     */
    readStateClass() {
      return `is-${getReadState(this.md)}`;
    },
    readFillStyle() {
      const pct =
        getReadState(this.md) === READ_STATE.UNREAD
          ? 0
          : getReadFillPercent(this.md);
      return { width: `${pct}%` };
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
 * Read state, matching the browser card. The slot is a fixed 10px so the
 * 3px/6px track can change thickness without moving anything below it; the
 * negative margins keep the track centered where the old 2px bar sat.
 */
.readState {
  display: flex;
  align-items: center;
  width: 100%;
  height: 10px;
  margin-top: -15px;
}

.readStateTrack {
  width: 100%;
  height: 3px;
  border-radius: 2px;
  overflow: hidden;
  background-color: transparent;
}

.readStateFill {
  width: 0;
  height: 100%;
  border-radius: inherit;
}

.is-reading .readStateTrack,
.is-finished .readStateTrack {
  background-color: rgba(var(--v-theme-text-disabled), 0.25);
}

.is-reading .readStateFill {
  background-color: rgb(var(--v-theme-primary));
}

.is-finished .readStateTrack {
  height: 6px;
  border-radius: 3px;
}

.is-finished .readStateFill {
  background-color: rgb(var(--v-theme-text-header));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .bookCoverWrapper {
    width: 100px;
  }

  .genericCoverImg {
    width: 100px;
  }

  .readState {
    margin-top: -3px;
  }
}
</style>
