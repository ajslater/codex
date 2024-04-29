<template>
  <div class="bookCover">
    <v-img :src="coverSrc" class="coverImg" />
    <div
      v-if="finished !== true"
      :class="{ unreadFlag: true, mixedreadFlag: finished === null }"
    />
    <span v-if="group !== 'c'" :class="childCountClasses">
      {{ childCount }}
    </span>
  </div>
</template>

<script>
import { getCoverSource } from "@/api/v3/cover.js";

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
    coverMtime: {
      type: String,
      required: true,
    },
    multiGroup: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      showPlaceholder: false,
    };
  },
  computed: {
    coverSrc() {
      return getCoverSource(this.coverPk, this.coverMtime);
    },
    childCountClasses() {
      return {
        childCount: true,
        multiGroup: this.multiGroup,
      };
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
@import "book-cover.scss";
.coverImg {
  height: $cover-height;
  width: $cover-width;
}
.coverImg {
  border-radius: 5px;
}
:deep(.coverImg .v-img__img) {
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
.multiGroup {
  border: thin dahsed white;
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
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .coverImg {
    height: $small-cover-height;
    width: $small-cover-width;
  }
}
</style>
