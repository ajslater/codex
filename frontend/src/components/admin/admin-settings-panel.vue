<template>
  <div>
    <header id="adminMenuHeader">
      <h3>Admin Status</h3>
    </header>
    <v-list-item-group>
      <v-list-item ref="browserLink" ripple :to="browserRoute">
        <v-list-item-content>
          <v-list-item-title> Browser </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
  </div>
</template>
<script>
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminSettingsPanel",
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

<style scoped lang="scss">
#adminMenuHeader {
  padding: 10px;
  padding-left: 15px;
}
</style>
