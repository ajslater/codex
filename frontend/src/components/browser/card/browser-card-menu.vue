<template>
  <v-menu offset-y top>
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
    <v-list nav>
      <v-list-item ripple @click="toggleRead">
        <v-list-item-content>
          <v-list-item-title>
            {{ markReadText }}
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapActions } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

export default {
  name: "BrowserContainerMenu",
  props: {
    group: {
      type: String,
      required: true,
    },
    pk: {
      type: Number,
      required: true,
    },
    finished: {
      type: Boolean,
    },
  },
  data() {
    return {
      mdiDotsVertical,
    };
  },
  computed: {
    markReadText: function () {
      const words = ["Mark"];
      if (this.group != "c") {
        words.push("Entire");
      }
      const groupNames = useBrowserStore().choices.groupNames;
      const groupName = groupNames[this.group];
      words.push(groupName);

      if (this.finished) {
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
      const params = {
        group: this.group,
        pk: this.pk,
      };
      this.setBookmarkFinished(params, !this.finished);
    },
  },
};
</script>
