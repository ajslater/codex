<template>
  <v-btn icon ripple title="Settings" @click.stop="openDrawer">
    <v-icon>{{ mdiMenu }}</v-icon>
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";

export default {
  name: "SettingsDrawerButton",
  data() {
    return {
      mdiMenu,
    };
  },
  methods: {
    openDrawer: function () {
      const val = !this.$store.state.isSettingsDrawerOpen;
      this.$store.commit("setIsSettingsDrawerOpen", val);
    },
  },
};
</script>
