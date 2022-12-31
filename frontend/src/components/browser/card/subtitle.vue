<template>
  <div class="browserLink cardSubtitle text-caption">
    <div v-if="headerName" class="headerName">
      {{ headerName }}
    </div>
    <div class="displayName">
      {{ displayName }}
    </div>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-if="orderValue" class="orderValue" v-html="orderValue" />
  </div>
</template>

<script>
import humanize from "humanize";
import { mapState } from "pinia";

import {
  formattedVolumeName,
  getFullComicName,
  getIssueName,
} from "@/comic-name";
import { DATE_FORMAT, DATETIME_FORMAT } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
const STAR_SORT_BY = new Set(["community_rating", "critical_rating"]);
const DATE_SORT_BY = new Set(["date"]);
const TIME_SORT_BY = new Set(["created_at", "updated_at"]);

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
    orderValue: function () {
      let ov = this.item.orderValue;
      if (
        this.orderByCache === undefined ||
        this.orderByCache === null ||
        this.orderByCache === "sort_name" ||
        (this.orderByCache === "path" && this.item.group === "f") ||
        ov === null ||
        ov === undefined
      ) {
        ov = "";
      } else if (this.orderByCache == "page_count") {
        const human = humanize.numberFormat(Number.parseInt(ov, 10), 0);
        ov = `${human} pages`;
      } else if (this.orderByCache == "size") {
        ov = humanize.filesize(Number.parseInt(ov, 10), 1024, 1);
      } else if (STAR_SORT_BY.has(this.orderByCache)) {
        ov = `★  ${ov}`;
      } else if (DATE_SORT_BY.has(this.orderByCache)) {
        const date = new Date(ov);
        ov = DATE_FORMAT.format(date);
      } else if (TIME_SORT_BY.has(this.orderByCache)) {
        const date = new Date(ov);
        ov = DATETIME_FORMAT.format(date).replace(", ", "<br />");
      }
      return ov;
    },
  },
  watch: {
    orderBy: function (to) {
      this.orderByCache = to;
    },
  },
  beforeCreate: function () {
    // Fixes empty order cache on first load
    // can't use computed value.
    this.orderByCache = useBrowserStore().settings.orderBy;
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@import "../../book-cover.scss";
.cardSubtitle {
  width: $cover-width;
  margin-top: 7px;
  padding-top: 3px;
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
.orderValue {
  color: rgb(var(--v-theme-textDisabled));
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .cardSubtitle {
    width: $small-cover-width;
  }
}
</style>
