<template>
  <v-menu v-model="showMenu" offset-y top>
    <template #activator="{ props }">
      <v-btn
        aria-label="action menu"
        class="browserCardMenuIcon cardControlButton"
        :icon="mdiDotsVertical"
        title="Action Menu"
        variant="text"
        v-bind="props"
        @click.prevent
      />
    </template>
    <div class="background-soft-highlight">
      <v-list-item
        v-if="item.group === 'c'"
        :title="markReadText"
        @click="toggleRead"
      />
      <ConfirmDialog
        v-else
        :button-text="markReadText"
        :title-text="markReadText"
        :confirm-text="confirmText"
        :object-name="itemName"
        @confirm="toggleRead"
        @cancel="showMenu = false"
      />
    </div>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserContainerMenu",
  components: {
    ConfirmDialog,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      mdiDotsVertical,
      showMenu: false,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      groupNames: (state) => state.choices.static.groupNames,
    }),
    verb() {
      return this.item.finished ? "Unread" : "Read";
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
