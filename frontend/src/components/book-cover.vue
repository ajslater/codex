<template>
  <div class="bookCover">
    <v-img :src="coverSrc" class="coverImg" :class="multiPkClasses" />
    <div
      v-if="finished !== true"
      :class="{ unreadFlag: true, mixedreadFlag: finished === null }"
    />
    <span v-if="group !== 'c'" class="childCount">
      {{ childCount }}
    </span>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { getCoverSrc } from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BookCover",
  props: {
    group: {
      type: String,
      required: true,
    },
    pks: {
      type: Array,
      required: true,
    },
    childCount: {
      type: Number,
      default: 1,
    },
    finished: {
      type: Boolean,
    },
    mtime: {
      type: Number,
      default: Date.now(),
    },
  },
  data() {
    return {
      showPlaceholder: false,
    };
  },
  computed: {
    ...mapState(useBrowserStore, ["coverSettings"]),
    coverSrc() {
      return getCoverSrc(
        { group: this.group, pks: this.pks },
        this.coverSettings,
        this.mtime,
      );
    },
    multiPkClasses() {
      const len = this.pks.length;
      const classes = {};
      if (len >= 4) {
        classes["stack4"] = true;
      } else if (len > 1) {
        classes[`stack${len}`] = true;
      }
      return classes;
    },
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
@use "sass:map";
@use "./book-cover" as bookcover;

.coverImg {
  height: bookcover.$cover-height;
  width: bookcover.$cover-width;
}
.coverImg {
  border-radius: 5px;
}
.coverImg :deep(.v-img__img) {
  object-position: top;
}

/* Top Row */
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
/* Flags */
$bookCoverShadow: rgba(0, 0, 0, 0.75);
$primary: rgb(var(--v-theme-primary));
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
    $bookCoverShadow 60%,
    $primary 60%
  );
  border-top-right-radius: 5px;
}
.mixedreadFlag {
  background: linear-gradient(
    45deg,
    transparent 50%,
    $bookCoverShadow 60%,
    $primary 60% 70%,
    transparent 70%,
    $bookCoverShadow 80%,
    $primary 80% 90%,
    transparent 90%
  );
}
.stack2 {
  box-shadow: 3px 3px #606060;
}
.stack3 {
  box-shadow:
    3px 3px #606060,
    6px 6px #404040;
}
.stack4 {
  box-shadow:
    3px 3px #606060,
    6px 6px #404040,
    9px 9px #202020;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .coverImg {
    height: bookcover.$small-cover-height;
    width: bookcover.$small-cover-width;
  }
}
</style>
