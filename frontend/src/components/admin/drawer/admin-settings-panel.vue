<template>
  <v-list-item ref="browserLink" :to="lastRoute">
    <v-list-item-title>
      <v-icon>{{ mdiBookshelf }}</v-icon
      >Browser
    </v-list-item-title>
  </v-list-item>
</template>
<script>
import { mdiBookshelf } from "@mdi/js";
import { mapGetters } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminSettingsPanel",
  data() {
    return {
      mdiBookshelf,
    };
  },
  computed: {
    ...mapGetters(useBrowserStore, ["lastRoute"]),
  },
};
</script>
