<template>
  <div>
    <img :src="`/static/${coverPath}`" class="coverImg" />
    <v-progress-linear
      class="progress"
      :value="progress"
      rounded
      background-color="inherit"
      height="2"
    />
  </div>
</template>

<script>
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
      required: true,
      default: 0,
    },
  },
  computed: {},
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
.coverImg {
  display: block;
  max-height: 180px;
  width: 120px;
  border-radius: 3px;
}
.progress {
}
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .coverImg {
    max-height: 150px;
    width: 100px;
  }
  .progress {
  }
}
</style>
