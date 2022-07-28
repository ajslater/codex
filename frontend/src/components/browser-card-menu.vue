<template>
  <v-menu offset-y top>
    <template #activator="{ on }">
      <v-icon
        class="browserCardActionMenu"
        aria-label="action menu"
        v-on="on"
        >{{ mdiDotsVertical }}</v-icon
      >
    </template>
    <v-list nav>
      <v-list-item v-if="group === 'c'" :href="downloadURL" download>
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
import { mapActions, mapState } from "vuex";

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
    };
  },
  computed: {
    ...mapState("reader", {
      downloadURL: function (state) {
        return getDownloadURL(this.pk, state.timestamp);
      },
    }),
    markReadText: function () {
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
  methods: {
    ...mapActions("browser", ["markedRead"]),
    toggleRead: function () {
      this.markedRead({
        group: this.group,
        pk: this.pk,
        finished: !this.finished,
      });
    },
  },
};
</script>

<style scoped lang="scss">
.browserCardActionMenu {
  position: absolute;
  bottom: 0px;
  right: 0px;
}
</style>
