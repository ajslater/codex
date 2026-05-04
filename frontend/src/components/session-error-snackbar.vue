<template>
  <v-snackbar
    v-model="show"
    color="error"
    timeout="-1"
    location="top"
    multi-line
  >
    {{ message }}
    <template #actions>
      <v-btn variant="text" @click="reload"> Reload </v-btn>
      <v-btn variant="text" @click="dismiss"> Dismiss </v-btn>
    </template>
  </v-snackbar>
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useCommonStore } from "@/stores/common";

export default {
  name: "SessionErrorSnackbar",
  computed: {
    ...mapState(useCommonStore, {
      message: (state) => state.sessionError,
    }),
    show: {
      get() {
        return Boolean(this.message);
      },
      set(value) {
        if (!value) {
          this.clearSessionError();
        }
      },
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["clearSessionError"]),
    dismiss() {
      this.clearSessionError();
    },
    reload() {
      globalThis.location.reload();
    },
  },
};
</script>
