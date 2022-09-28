<template>
  <v-menu v-model="showMenu" offset-y top>
    <template #activator="{ on }">
      <v-btn
        aria-label="action menu"
        class="browserCardMenuIcon"
        icon
        title="Action Menu"
        v-on="on"
        @click.prevent
      >
        <v-icon>
          {{ mdiDotsVertical }}
        </v-icon>
      </v-btn>
    </template>
    <v-list-item-group class="background-soft-highlight">
      <v-list-item v-if="item.group === 'c'" ripple @click="toggleRead">
        <v-list-item-content>
          <v-list-item-title>
            {{ markReadText }}
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <ConfirmMarkReadDialog
        v-else
        :text="markReadText"
        :name="item.name"
        @confirm="toggleRead"
        @cancel="showMenu = false"
      />
    </v-list-item-group>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ConfirmMarkReadDialog from "@/components/browser/confirm-mark-read-dialog.vue";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

export default {
  name: "BrowserContainerMenu",
  components: {
    ConfirmMarkReadDialog,
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
    markReadText: function () {
      const words = ["Mark"];
      if (this.item.group != "c") {
        words.push("Entire");
      }
      let groupName = this.groupNames[this.item.group];
      if (this.item.group !== "s") {
        groupName = groupName.slice(0, -1);
      }
      words.push(groupName);

      if (this.item.finished) {
        words.push("Unread");
      } else {
        words.push("Read");
      }
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
