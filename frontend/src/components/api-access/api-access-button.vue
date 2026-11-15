<template>
  <v-btn
    id="apiAccessButton"
    icon
    size="small"
    variant="plain"
    title="OPDS, KOReader sync and API keys"
    @click="showApiAccessDialog = true"
  >
    <v-icon>{{ mdiRss }}</v-icon>
    OPDS &amp; APIs
  </v-btn>
</template>

<script>
import { mdiRss } from "@mdi/js";
import { mapWritableState } from "pinia";

import { useAuthStore } from "@/stores/auth";

export default {
  name: "ApiAccessButton",
  data() {
    return { mdiRss };
  },
  computed: {
    ...mapWritableState(useAuthStore, ["showApiAccessDialog"]),
  },
};
</script>

<style scoped lang="scss">
#apiAccessButton {
  display: block;
  width: 100%;
  color: rgb(var(--v-theme-text-secondary));
}
</style>
