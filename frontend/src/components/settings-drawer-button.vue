<template>
  <v-btn icon ripple title="Settings" @click.stop="toggleSettingsDrawerOpen">
    <v-icon>{{ mdiMenu }}</v-icon>
  </v-btn>
</template>

<script>
import { mdiMenu } from "@mdi/js";
import { mapMutations } from "vuex";

export default {
  name: "SettingsDrawerButton",
  data() {
    return {
      mdiMenu,
    };
  },
  methods: {
    ...mapMutations(["toggleSettingsDrawerOpen"]),
  },
};
</script>
