<template>
  <v-menu ref="browserSettingsMenu" v-model="menuOpen" offset-y>
    <template #activator="{ on }">
      <v-btn icon ripple title="Settings" v-on="on">
        <v-icon>{{ mdiDotsVertical }}</v-icon>
      </v-btn>
    </template>
    <v-list-item-group id="settingsMenu" ripple>
      <BrowserSettingsDialog @sub-dialog-open="close" />
      <AuthDialog @sub-dialog-open="close" />
      <v-list-item v-if="isOpenToSee" @click="reload">
        <v-list-item-content>
          <v-list-item-title> Reload Libraries</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapGetters } from "vuex";

import AuthDialog from "@/components/auth-dialog";
import BrowserSettingsDialog from "@/components/browser-settings-dialog";

export default {
  name: "BrowserSettingsMenu",
  components: {
    AuthDialog,
    BrowserSettingsDialog,
  },
  data() {
    return {
      mdiDotsVertical,
      menuOpen: false,
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  methods: {
    reload: function () {
      this.$store.dispatch("browser/browserOpened", this.$route.params);
    },
    close: function () {
      // workaround for menu not closing when sub dialogs open.
      this.menuOpen = false;
    },
  },
};
</script>

<style scoped lang="scss">
#settingsMenu {
  background-color: #121212;
}
</style>
