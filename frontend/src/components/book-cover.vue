<template>
  <div class="bookCoverWrapper">
    <div class="bookCover">
      <div class="coverImgWrapper">
        <v-img :key="coverSrc" :src="coverSrc" class="coverImg" contain>
          <template #placeholder>
            <v-progress-circular
              v-if="showPlaceholder"
              indeterminate
              size="109"
              :color="$vuetify.theme.current.colors.primary"
              aria-label="loading"
              class="coverPlaceholder"
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
import { mapState } from "pinia";

import { getCoverSource } from "@/api/v3/cover.js";
import { useBrowserStore } from "@/stores/browser";

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
    ...mapState(useBrowserStore, {
      coverSrc: function (state) {
        return getCoverSource(this.coverPk, state.page.coversTimestamp);
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
@use "vuetify/styles/settings/variables" as vuetify;
@import "book-cover.scss";
.coverImgWrapper {
  height: $cover-height;
  width: $cover-width;
}
.coverImg {
  display: block;
  height: 100%;
  width: 100%;
  border-radius: 5px;
}
.coverPlaceholder {
  height: 100% !important;
  width: 66% !important;
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
  background-color: rgb(var(--v-theme-background));
  color: rbg(var(--v-theme-textPrimary));
}
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
    rgba(var(--v-theme-bookCoverColor), var(--v-theme-bookCoverOpacity)) 60%,
    var(--v-primary-base) 60%
  );
  border-radius: 5px;
}
.mixedreadFlag {
  background: linear-gradient(
    45deg,
    transparent 50%,
    rgba(var(--v-theme-bookCoverColor), var(--v-theme-bookCoverOpacity)) 60%,
    var(--v-primary-base) 60%,
    var(--v-primary-base) 70%,
    transparent 70%,
    rgba(var(--v-theme-bookCoverColor), var(--v-theme-bookCoverOpacity)) 60%,
    var(--v-primary-base) 80%,
    var(--v-primary-base) 90%,
    transparent 90%
  );
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .coverImgWrapper {
    height: $small-cover-height;
    width: $small-cover-width;
  }
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#browsePaneContainer .coverImg .v-image__placeholder {
  top: 50%;
  left: 50%;
  transform: translate(-33%, -50%);
}
#browsePaneContainer .coverImgWrapper .v-image__image {
  background-position-y: top !important;
}
</style>
