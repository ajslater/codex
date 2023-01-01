<template>
  <div class="browserLink cardSubtitle text-caption">
    <div v-if="headerName" class="headerName">
      {{ headerName }}
    </div>
    <div class="displayName">
      {{ displayName }}
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import {
  formattedVolumeName,
  getFullComicName,
  getIssueName,
} from "@/comic-name";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserCardSubtitle",
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  orderByCache: "sort_name",
  computed: {
    ...mapState(useBrowserStore, {
      orderBy: (state) => state.settings.orderBy,
      zeroPad: (state) => state.page.zeroPad,
    }),
    headerName: function () {
      let hn;
      switch (this.item.group) {
        case "i":
          hn = this.item.publisherName;
          break;

        case "v":
          hn = this.item.seriesName;
          break;
        case "c":
          hn =
            this.$route.params.group === "f"
              ? getFullComicName(this.item, this.zeroPad)
              : getIssueName(this.item, this.zeroPad);
          break;
        default:
          hn = "";
      }
      return hn;
    },
    displayName: function () {
      return this.item.group === "v"
        ? formattedVolumeName(this.item.name)
        : this.item.name;
    },
    linkLabel: function () {
      let label = "";
      label += this.item.group === "c" ? "Read" : "Browse to";
      label += " " + this.headerName;
      return label;
    },
  },
};
</script>

<style scoped lang="scss">
.cardSubtitle {
  width: 100%;
  margin-top: 10px;
  text-align: center;
}
.headerName {
  padding-top: 5px;
  color: rgb(var(--v-theme-textDisabled));
}
.headerName,
.displayName {
  overflow-wrap: break-word;
}
.displayName {
  min-height: 1em;
}
</style>
