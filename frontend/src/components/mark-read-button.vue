<template>
  <ConfirmDialog
    v-if="show"
    :button="button"
    :button-text="markReadText"
    :confirm="confirm"
    :confirm-text="confirmText"
    :prepend-icon="icon"
    :title-text="markReadText"
    :text="itemName"
    @confirm="toggleRead"
  />
</template>

<script>
import { mdiBookmarkCheckOutline, mdiBookmarkMinusOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useBrowserStore } from "@/stores/browser";

const CHILD_WARNING_LIMIT = 1;

export default {
  name: "MarkReadButton",
  components: { ConfirmDialog },
  props: {
    button: {
      type: Boolean,
      default: false,
    },
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useBrowserStore, ["collectionNames"]),
    verb() {
      return this.item.finished ? "Unread" : "Read";
    },
    confirm() {
      /*
       * ``childCount`` is the wire key browser card items carry; the
       * metadata panel builds its item with the same key. Comic cards
       * carry no child key at all, so they never warn.
       */
      return (this.item.childCount ?? 0) > CHILD_WARNING_LIMIT;
    },
    show() {
      return this.item?.ids?.length > 0 && !this.item.ids.includes(0);
    },
    icon() {
      return this.item.finished
        ? mdiBookmarkMinusOutline
        : mdiBookmarkCheckOutline;
    },
    confirmText() {
      if (!this.confirm) {
        return "";
      }
      return `Mark ${this.verb}`;
    },
    markReadText() {
      const words = ["Mark"];
      if (this.item.collection != "comics") {
        words.push("Entire");
      }
      const collectionName = this.collectionNames[this.item.collection];
      words.push(collectionName, this.verb);
      return words.join(" ");
    },
    itemName() {
      return this.item.name || "(Empty)";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setBookmarkFinished"]),
    toggleRead: function () {
      this.setBookmarkFinished(this.item, !this.item.finished);
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  :deep(.v-icon) {
    color: rgb(var(--v-theme-text-disabled));
  }
}
</style>
