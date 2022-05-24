<template>
  <v-btn icon ripple title="Settings" v-on="$listeners">
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
};
</script>
