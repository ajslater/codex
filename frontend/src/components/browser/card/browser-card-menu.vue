<template>
  <v-menu v-model="showMenu" offset-y top>
    <template #activator="{ props }">
      <v-btn
        aria-label="action menu"
        class="browserCardMenuIcon cardControlButton"
        icon
        title="Action Menu"
        variant="text"
        v-bind="props"
        @click.prevent
      >
        <v-icon>
          {{ mdiDotsVertical }}
        </v-icon>
      </v-btn>
    </template>
    <div class="background-soft-highlight">
      <v-list-item v-if="item.group === 'c'" @click="toggleRead">
        <v-list-item-title>
          {{ markReadText }}
        </v-list-item-title>
      </v-list-item>
      <ConfirmDialog
        v-else
        :button-text="markReadText"
        :title-text="markReadText"
        :confirm-text="confirmText"
        :object-name="item.name"
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
import { useCommonStore } from "@/stores/common";

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
  },
  methods: {
    ...mapActions(useBrowserStore, ["setBookmarkFinished"]),
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    toggleRead: function () {
      this.setBookmarkFinished(this.item, !this.item.finished);
      this.showMenu = false;
    },
  },
};
</script>

<style scoped lang="scss"></style>
