<template>
  <v-menu offset-y top>
    <template #activator="{ on }">
      <v-icon class="actionMenu" v-on="on">{{ mdiDotsVertical }}</v-icon>
    </template>
    <v-list nav>
      <v-list-item v-if="group === 'c'" :href="downloadURL">
        <v-list-item-content> Download Comic </v-list-item-content>
      </v-list-item>
      <v-list-item @click="toggleRead">
        <v-list-item-content> {{ markReadText }}</v-list-item-content>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";

import { getDownloadURL } from "@/api/v1/metadata";

const containerNames = {
  p: "Publisher",
  i: "Imprint",
  s: "Series",
  v: "Volume",
  c: "Issue",
};

export default {
  name: "BrowseContainerMenu",
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
    markRead: function (group, pk, finished) {
      this.$store.dispatch("browser/markRead", { group, pk, finished });
    },
    toggleRead: function () {
      this.$store.dispatch("browser/markRead", {
        group: this.group,
        pk: this.pk,
        finished: !this.finished,
      });
    },
    getMarkReadText: function () {
      let text = "Mark ";
      if (this.group != "c") {
        text += "Entire ";
      }
      text += containerNames[this.group] + " ";

      if (this.finished) {
        text += "Unread";
      } else {
        text += "Read";
      }
      return text;
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
