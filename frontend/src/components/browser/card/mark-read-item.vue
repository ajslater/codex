<template>
  <CodexListItem
    v-if="item.group === 'c'"
    :prepend-icon="icon"
    :title="markReadText"
    @click="toggleRead"
  />
  <ConfirmDialog
    v-else
    :button="false"
    :prepend-icon="icon"
    :button-text="markReadText"
    :title-text="markReadText"
    :confirm-text="confirmText"
    :text="itemName"
    @confirm="toggleRead"
    @cancel="showMenu = false"
  />
</template>

<script>
import { mdiBookmarkCheckOutline, mdiBookmarkMinusOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CodexListItem from "@/components/codex-list-item.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserMarkReadItem",
  components: {
    ConfirmDialog,
    CodexListItem,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useBrowserStore, {
      groupNames: (state) => state.choices.static.groupNames,
    }),
    verb() {
      return this.item.finished ? "Unread" : "Read";
    },
    icon() {
      return this.item.finished
        ? mdiBookmarkMinusOutline
        : mdiBookmarkCheckOutline;
    },
    confirmText() {
      return `Mark ${this.verb}`;
    },
    markReadText() {
      const words = ["Mark"];
      if (this.item.group != "c") {
        words.push("Entire");
      }
      let groupName = this.groupNames[this.item.group];
      if (this.item.group !== "s") {
        groupName = groupName.slice(0, -1);
      }
      words.push(groupName, this.verb);
      return words.join(" ");
    },
    itemName() {
      return this.item.name ? this.item.name : "(Empty)";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setBookmarkFinished"]),
    toggleRead: function () {
      this.setBookmarkFinished(this.item, !this.item.finished);
      this.showMenu = false;
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
