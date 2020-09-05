<template>
  <main id="main">
    <div id="fofWrapper">
      <h1 id="fof">404</h1>
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
#fofWrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}

#fofWrapper {
  position: fixed;
}

#fof {
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
