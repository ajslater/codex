<template>
  <main id="main">
    <div id="fourOhFourWrapper">
      <h1 id="fourOhFour">404</h1>
    </div>
    <div id="foreground">
      <h1 id="notFound">Page Not Found</h1>
      <div>
        <router-link :to="{ name: 'home' }"
          ><h2>Codex Browser Home</h2></router-link
        >
      </div>
    </div>
  </main>
</template>

<script>
export default {
  name: "NotFound",
  data() {
    return {};
  },
};
</script>

<style scoped lang="scss">
#main,
#fourOhFourWrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}

#fourOhFourWrapper {
  position: fixed;
}

#fourOhFour {
  color: gray;
  stroke: gray;
  fill: gray;
  float: left;
  margin: 0px;
  font-size: 70vh;
  opacity: 25%;
}
#foreground {
  text-align: center;
  z-index: 100;
}
</style>
