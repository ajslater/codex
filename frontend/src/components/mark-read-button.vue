<template>
  <v-btn v-if="show && !confirm && button" @click="toggleRead">
    <v-icon>{{ icon }}</v-icon>
    {{ markReadText }}
  </v-btn>
  <CodexListItem
    v-else-if="item.group === 'c'"
    :prepend-icon="icon"
    :title="markReadText"
    @click="toggleRead"
  />
  <ConfirmDialog
    v-else
    :button="button"
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

const CHILD_WARNING_LIMIT = 1;

export default {
  name: "MarkReadButton",
  components: {
    ConfirmDialog,
    CodexListItem,
  },
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
    ...mapState(useBrowserStore, {
      groupNames: (state) => state.choices.static.groupNames,
    }),
    verb() {
      return this.item.finished ? "Unread" : "Read";
    },
    confirm() {
      return this.item.children > CHILD_WARNING_LIMIT;
    },
    show() {
      return (
        this.item.ids && this.item.ids.length > 0 && !this.item.ids.includes(0)
      );
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
