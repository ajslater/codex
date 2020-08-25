<template>
  <div class="bookCover">
    <div class="coverImgWrapper">
      <v-img :src="coverSrc" class="coverImg" contain>
        <template #placeholder>
          <v-progress-circular
            v-if="showPlaceholder"
            indeterminate
            size="48"
            color="#cc7b19"
          />
        </template>
      </v-img>
    </div>
    <v-progress-linear
      :value="progress"
      rounded
      background-color="inherit"
      height="2"
    />
  </div>
</template>

<script>
import { getCoverSrc } from "@/api/browser";

export default {
  name: "BookCover",
  props: {
    coverPath: {
      type: String,
      required: true,
      default: "",
    },
    progress: {
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
    coverSrc: function () {
      return getCoverSrc(this.coverPath);
    },
  },
  mounted: function () {
    this.delayPlaceholder();
  },
  methods: {
    delayPlaceholder: function () {
      setTimeout(() => {
        this.showPlaceholder = true;
      }, 1000);
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
.coverImgWrapper {
  height: 180px;
  width: 120px;
}
.coverImg {
  display: block;
  min-height: 48px; /* for the placeholder :/ */
  max-height: 180px;
  width: 120px;
  border-radius: 5px;
}
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .coverImgWrapper {
    height: 150px;
    width: 100px;
  }
  .coverImg {
    max-height: 150px;
    width: 100px;
  }
}
</style>
