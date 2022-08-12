<template>
  <div class="bookCoverWrapper">
    <div class="bookCover">
      <div class="coverImgWrapper">
        <v-img :key="coverSrc" :src="coverSrc" class="coverImg" contain>
          <template #placeholder>
            <v-progress-circular
              v-if="showPlaceholder"
              indeterminate
              size="48"
              color="#cc7b19"
              aria-label="loading"
            />
          </template>
        </v-img>
      </div>
      <div class="bookCoverOverlayTopRow">
        <div
          v-if="finished !== true"
          :class="{ unreadFlag: true, mixedreadFlag: finished === null }"
        />

        <span v-if="group !== 'c'" class="childCount">
          {{ childCount }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

import { getCoverSource } from "@/api/v2/cover";

export default {
  name: "BookCover",
  props: {
    group: {
      type: String,
      required: true,
    },
    childCount: {
      type: Number,
      default: 1,
    },
    finished: {
      type: Boolean,
    },
    coverPk: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      showPlaceholder: false,
    };
  },
  computed: {
    ...mapState("browser", {
      coverSrc: function (state) {
        return getCoverSource(this.coverPk, state.coversTimestamp);
      },
    }),
  },
  mounted: function () {
    this.delayPlaceholder();
  },
  methods: {
    delayPlaceholder: function () {
      setTimeout(() => {
        this.showPlaceholder = true;
      }, 2000);
    },
  },
};
</script>

<style scoped lang="scss">
@import "book-cover.scss";
.bookCoverWrapper {
}
.coverImgWrapper {
  height: $cover-height;
}
.coverImg {
  display: block;
  min-height: 48px; /* for the placeholder :/ */
  max-height: $cover-height;
  border-radius: 5px;
}
.coverImgWrapper,
.coverImg {
  width: $cover-width;
}
.bookCoverOverlayTopRow {
  height: 15%;
  display: flex;
  opacity: 1;
  width: 100%;
}
.childCount {
  position: absolute;
  top: 0px;
  left: 0px;
  min-width: 1.5rem;
  padding: 0rem 0.25rem 0rem 0.25rem;
  text-align: center;
  border-radius: 50%;
  background-color: black;
  color: white;
}
@import "~vuetify/src/styles/styles.sass";
.unreadFlag {
  position: absolute;
  top: 0;
  right: 0;
  display: block;
  width: 24px;
  height: 24px;
  background: linear-gradient(
    45deg,
    transparent 50%,
    rgba(0, 0, 0, 0.5) 60%,
    var(--v-primary-base) 60%
  );
  border-radius: 5px;
}
.mixedreadFlag {
  background: linear-gradient(
    45deg,
    transparent 50%,
    rgba(0, 0, 0, 0.5) 60%,
    var(--v-primary-base) 60%,
    var(--v-primary-base) 70%,
    transparent 70%,
    rgba(0, 0, 0, 0.5) 80%,
    var(--v-primary-base) 80%,
    var(--v-primary-base) 90%,
    transparent 90%
  );
}

@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .coverImgWrapper {
    height: $small-cover-height;
  }
  .coverImg {
    max-height: $small-cover-height;
  }
  .coverImgWrapper,
  .coverImg {
    width: $small-cover-width;
  }
}
</style>
