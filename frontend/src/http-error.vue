<template>
  <main id="main">
    <div id="httpCodeWrapper">
      <h1 id="httpCode">{{ code }}</h1>
    </div>
    <div id="foreground">
      <h1 id="title">{{ title }}</h1>
      <div>
        <router-link :to="{ name: 'home' }"><h2>Codex Home</h2></router-link>
      </div>
    </div>
  </main>
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
      return +this.$router.currentRoute.params.code;
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
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  position: fixed;
}

#title {
  color: gray;
  stroke: gray;
  fill: gray;
  float: left;
  margin: 0px;
  font-size: 10vw;
  opacity: 25%;
}
#foreground {
  text-align: center;
  z-index: 100;
}
</style>
