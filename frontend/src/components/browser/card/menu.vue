<template>
  <v-menu offset-y top>
    <template #activator="{ on }">
      <v-icon
        class="browserCardMenuIcon"
        aria-label="action menu"
        right
        v-on="on"
        @click.prevent
        >{{ mdiDotsVertical }}</v-icon
      >
    </template>
    <v-list nav>
      <v-list-item v-if="group === 'c'" :href="downloadURL" ripple download>
        <v-list-item-content>
          <v-list-item-title>Download Comic</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
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
import { mapActions, mapState } from "pinia";

import { getDownloadURL } from "@/api/v3/reader.js";
import { useBrowserStore } from "@/stores/browser";
import { useReaderStore } from "@/stores/reader";

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
    ...mapState(useReaderStore, {
      downloadURL: function (state) {
        return getDownloadURL(this.pk, state.timestamp);
      },
    }),
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
