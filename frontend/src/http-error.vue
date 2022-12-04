<template>
  <v-main id="main">
    <div id="httpCodeWrapper">
      <h1 id="httpCode">
        {{ code }}
      </h1>
    </div>
    <div id="foreground">
      <h1 id="title">
        {{ title }}
      </h1>
      <div>
        <router-link :to="{ name: 'home' }">
          <h2>Codex Home</h2>
        </router-link>
      </div>
    </div>
  </v-main>
</template>

<script>
const TITLES = {
  400: "Bad Request",
  403: "Forbidden",
  404: "Page Not Found",
  500: "Server Error",
};
Object.freeze(TITLES);

export default {
  name: "HttpError",
  data() {
    return {};
  },
  computed: {
    code: function () {
      return +this.$route.params.code;
    },
    title: function () {
      let title = TITLES[this.code];
      if (!title) {
        title = "Unknown Error";
      }
      return title;
    },
  },
};
</script>

<style scoped lang="scss">
#main,
#httpCodeWrapper {
  width: 100vw;
  height: 100vh;
}
#httpCode,
#foreground {
  position: absolute;
  top: 25%;
  left: 50%;
  transform: translateX(-50%) translateY(-25%);
}
#httpCode {
  padding-top: 2rem;
}

#foreground {
  text-align: center;
  z-index: 100;
}
#title {
  color: rgb(var(--v-theme-textDisabled));
  stroke: rgb(var(--v-theme-textDisabled));
  fill: rgb(var(--v-theme-textDisabled));
  margin: 0px;
  font-size: 6vw;
  opacity: 25%;
}
</style>
