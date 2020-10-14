<template>
  <v-menu offset-y top>
    <template #activator="{ on }">
      <v-icon class="actionMenu" v-on="on">{{ mdiDotsVertical }}</v-icon>
    </template>
    <v-list nav>
      <v-list-item v-if="group === 'c'" :href="downloadURL">
        <v-list-item-content>
          <v-list-item-title>Download Comic</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <v-list-item @click="toggleRead">
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

import { getDownloadURL } from "@/api/v2/comic";

const groupNames = {
  p: "Publisher",
  i: "Imprint",
  s: "Series",
  v: "Volume",
  c: "Issue",
  f: "Folder",
};

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
      downloadURL: getDownloadURL(this.pk),
      markReadText: this.getMarkReadText(),
    };
  },
  methods: {
    toggleRead: function () {
      this.$store.dispatch("browser/markedRead", {
        group: this.group,
        pk: this.pk,
        finished: !this.finished,
      });
    },
    getMarkReadText: function () {
      const words = ["Mark"];
      if (this.group != "c") {
        words.push("Entire");
      }
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
};
</script>

<style scoped lang="scss">
.actionMenu {
  position: absolute;
  bottom: 3px;
  right: 3px;
}
</style>
