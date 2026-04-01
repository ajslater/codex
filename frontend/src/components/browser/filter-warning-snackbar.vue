<template>
  <v-snackbar
    v-model="show"
    color="warning"
    timeout="5000"
    location="bottom"
  >
    Some filters could not fully apply: {{ fields }}
    <template #actions>
      <v-btn variant="text" @click="clearSavedSettingsSnackbar">
        Close
      </v-btn>
    </template>
  </v-snackbar>
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "FilterWarningSnackbar",
  computed: {
    ...mapState(useBrowserStore, {
      filterWarnings: (state) => state.savedSettingsSnackbar,
    }),
    fields() {
      return (this.filterWarnings || []).join(", ");
    },
    show: {
      get() {
        return this.filterWarnings && this.filterWarnings.length > 0;
      },
      set(value) {
        if (!value) {
          this.clearSavedSettingsSnackbar();
        }
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["clearSavedSettingsSnackbar"]),
  },
};
</script>
