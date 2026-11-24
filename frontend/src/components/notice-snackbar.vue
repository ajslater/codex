<template>
  <v-snackbar
    :key="noticeKey"
    v-model="show"
    class="noticeSnackbar"
    :color="notice.error ? 'error' : undefined"
    :timeout="notice.error || notice.action ? ERROR_TIMEOUT : TIMEOUT"
    location="bottom"
    multi-line
  >
    {{ notice.text }}
    <template #actions>
      <v-btn
        v-if="notice.action"
        class="noticeAction"
        variant="text"
        @click="runAction"
        >{{ notice.action.label }}</v-btn
      >
      <v-btn variant="text" @click="clearNotice">Dismiss</v-btn>
    </template>
  </v-snackbar>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useCommonStore } from "@/stores/common";

/*
 * Shows the common store's notice: a confirmation or error for an action
 * taken outside a form, with a button when it offers a next step. Errors
 * stay up longer, to be read.
 */
export default {
  name: "NoticeSnackbar",
  data() {
    // A new key per notice remounts the snackbar, which starts its timer
    // only when it opens: a notice replacing one still showing would
    // otherwise close on the first one's time.
    return { TIMEOUT: 4000, ERROR_TIMEOUT: 8000, noticeKey: 0 };
  },
  computed: {
    ...mapState(useCommonStore, ["notice"]),
    show: {
      get() {
        return Boolean(this.notice.text);
      },
      set(value) {
        if (!value) this.clearNotice();
      },
    },
  },
  watch: {
    notice() {
      this.noticeKey += 1;
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["clearNotice"]),
    runAction() {
      const { run } = this.notice.action;
      this.clearNotice();
      run();
    },
  },
};
</script>
