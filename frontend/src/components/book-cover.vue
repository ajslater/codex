<template>
  <div class="bookCover">
    <v-img
      :src="coverSrc"
      class="coverImg"
      :class="multiPkClasses"
      position="top"
    />
    <span v-if="group !== 'c'" class="childCount">
      {{ childCount }}
    </span>
  </div>
</template>

<script>
import { getCoverSrc } from "@/api/v3/browser";

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
    coverPk: {
      type: Number,
      default: 0,
    },
    coverCustomPk: {
      type: Number,
      default: 0,
    },
    childCount: {
      type: Number,
      default: 1,
    },
    mtime: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      showPlaceholder: false,
    };
  },
  computed: {
    coverSrc() {
      return getCoverSrc(
        { coverPk: this.coverPk, coverCustomPk: this.coverCustomPk },
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
  border-radius: 5px;
}

/* Child Count - top right */
.childCount {
  position: absolute;
  top: 0px;
  right: 0px;
  min-width: 1.5rem;
  padding: 0rem 0.25rem 0rem 0.25rem;
  text-align: center;
  border-radius: 50%;
  background-color: rgb(var(--v-theme-background));
  color: rgb(var(--v-theme-textPrimary));
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
