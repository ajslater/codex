<template>
  <v-main v-if="isAuthorized" id="httpError">
    <AppBanner />
    <h1 id="httpCode">
      {{ code }}
    </h1>
    <h1 id="title">
      {{ title }}
    </h1>
    <router-link id="link" :to="{ name: 'home' }">
      <h2>Codex Home</h2>
    </router-link>
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mapState } from "pinia";

import AppBanner from "@/components/banner.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";

const TITLES = {
  400: "Bad Request",
  403: "Forbidden",
  404: "Page Not Found",
  500: "Server Error",
};
Object.freeze(TITLES);

export default {
  name: "HttpError",
  components: {
    AppBanner,
    Unauthorized,
  },
  data() {
    return {};
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthorized"]),
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
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#httpError {
  padding-top: max(20px, env(safe-area-inset-top));
  padding-left: max(20px, env(safe-area-inset-left));
  padding-right: max(20px, env(safe-area-inset-right));
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

#httpCode,
#title,
#link {
  position: absolute;
  left: 50%;
  transform: translateX(-50%) translateY(-25%);
}

#httpCode,
#title {
  top: 25%;
}

#httpCode {
  z-index: 100;
  padding-top: 1em;
}

#title {
  text-align: center;
  font-size: 6vw;
  color: rgb(var(--v-theme-textDisabled));
  stroke: rgb(var(--v-theme-textDisabled));
  fill: rgb(var(--v-theme-textDisabled));
  opacity: 25%;
}

#link {
  bottom: 50%;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #title {
    font-size: 32vw;
  }
}
</style>
