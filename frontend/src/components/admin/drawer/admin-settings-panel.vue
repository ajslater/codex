<template>
  <v-list-item ref="browserLink" :to="browserRoute">
    <v-list-item-title>
      <v-icon>{{ mdiBookshelf }}</v-icon
      >Browser
    </v-list-item-title>
  </v-list-item>
</template>
<script>
import { mdiBookshelf } from "@mdi/js";
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminSettingsPanel",
  data() {
    return {
      mdiBookshelf,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      browserRoute: (state) =>
        state.page.routes.last
          ? { name: "browser", params: state.page.routes.last }
          : { name: "home" },
    }),
  },
};
</script>
