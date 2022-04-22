<template>
  <v-lazy transition="scale-transition" class="browserTile">
    <div class="browserTileLazyWrapper">
      <div class="browserCardCoverWrapper">
        <BookCover
          :cover-path="item.coverPath"
          :updated-at="item.coverUpdatedAt"
          :group="item.group"
          :child-count="item.childCount"
          :finished="item.finished"
        />
        <div class="cardCoverOverlay">
          <router-link class="browserLink" :to="toRoute">
            <div class="cardCoverOverlayTopMiddleRow">
              <v-icon v-if="item.group === 'c'">{{ mdiEye }}</v-icon>
            </div>
          </router-link>
          <div class="cardCoverOverlayBottomRow">
            <MetadataButton
              class="metadataButton"
              :group="item.group"
              :pk="item.pk"
              :children="item.childCount"
            />
            <BrowserCardMenu
              class="browserCardMenu"
              :group="item.group"
              :pk="item.pk"
              :finished="item.finished"
            />
          </div>
        </div>
      </div>
      <v-progress-linear
        class="bookCoverProgress"
        :value="item.progress"
        rounded
        background-color="inherit"
        height="2"
      />
      <router-link class="browserLink cardSubtitle text-caption" :to="toRoute">
        <div v-if="headerName" class="headerName">{{ headerName }}</div>
        <div class="displayName">{{ displayName }}</div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-if="orderValue" class="orderValue" v-html="orderValue" />
      </router-link>
    </div>
  </v-lazy>
</template>

<script>
// import { mdiChevronLeft } from "@mdi/js";
import { mdiEye } from "@mdi/js";
import humanize from "humanize";
import { mapState } from "vuex";

import BookCover from "@/components/book-cover";
import BrowserCardMenu from "@/components/browser-card-menu";
import {
  formattedVolumeName,
  getFullComicName,
  getIssueName,
} from "@/components/comic-name";
import { DATE_FORMAT, DATETIME_FORMAT } from "@/components/datetime";
import MetadataButton from "@/components/metadata-dialog";
import { getReaderRoute } from "@/router/route";

const STAR_SORT_BY = new Set(["community_rating", "critical_rating"]);
const DATE_SORT_BY = new Set(["date"]);
const TIME_SORT_BY = new Set(["created_at", "updated_at"]);

export default {
  name: "BrowserCard",
  components: {
    BookCover,
    BrowserCardMenu,
    MetadataButton,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      mdiEye,
    };
  },
  // Stored here instead of data to be non-reactive
  orderByCache: "sort_name",
  computed: {
    ...mapState("browser", {
      orderBy: (state) => state.settings.orderBy,
      zeroPad: (state) => state.zeroPad,
    }),
    headerName: function () {
      let headerName;
      switch (this.item.group) {
        case "c":
          headerName =
            !Number(this.$route.params.pk) || this.$route.params.group === "f"
              ? (headerName = getFullComicName(this.item, this.zeroPad))
              : (headerName = getIssueName(this.item, this.zeroPad));
          break;

        case "i":
          headerName = this.item.publisherName;
          break;

        case "v":
          headerName = this.item.seriesName;
          break;

        default:
          headerName = "";
      }
      return headerName;
    },
    displayName: function () {
      return this.item.group === "v"
        ? formattedVolumeName(this.item.name)
        : this.item.name;
    },
    orderValue: function () {
      let ov = this.item.orderValue;
      if (
        this.orderByCache === "sort_name" ||
        this.orderByCache === null ||
        this.orderByCache === undefined ||
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
        ov = `${ov} stars`;
      } else if (DATE_SORT_BY.has(this.orderByCache)) {
        const date = new Date(ov);
        ov = DATE_FORMAT.format(date);
      } else if (TIME_SORT_BY.has(this.orderByCache)) {
        const date = new Date(ov);
        ov = DATETIME_FORMAT.format(date).replace(",", "<br/>");
      }
      return ov;
    },
    toRoute: function () {
      return this.item.group === "c"
        ? getReaderRoute(
            this.item.pk,
            this.item.bookmark,
            this.item.read_ltr,
            this.item.page_count
          )
        : {
            name: "browser",
            params: { group: this.item.group, pk: this.item.pk, page: 1 },
          };
    },
  },
  watch: {
    orderBy: function (to) {
      this.orderByCache = to;
    },
  },
  beforeCreate: function () {
    // Fixes empty order cache on first load
    this.orderByCache = this.$store.state.browser.settings.orderBy;
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
.browserTile {
  display: inline-flex;
  flex: 1;
  margin: 16px;
  text-align: center;
}
.browserTileLazyWrapper {
  width: 120px;
}
.browserCardCoverWrapper {
  position: relative;
}
.cardCoverOverlay {
  position: absolute;
  top: 0px;
  height: 100%;
  width: 100%;
  text-align: center;
  border-radius: 5px;
  border: solid thin transparent;
}
.browserCardCoverWrapper:hover > .cardCoverOverlay {
  background-color: rgba(0, 0, 0, 0.5);
  border: solid thin #cc7b19;
}
.cardCoverOverlay > * {
  width: 100%;
}
.browserCardCoverWrapper:hover > .cardCoverOverlay * {
  /* optimize-css-assets-webpack-plugin / cssnano bug destroys % values. 
     use decimals instead.
     https://github.com/NMFR/optimize-css-assets-webpack-plugin/issues/118
  */
  opacity: 1;
}
.cardCoverOverlayTopMiddleRow {
  height: 70%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cardCoverOverlayTopMiddleRow,
.cardCoverOverlayBottomRow {
  opacity: 0;
}
.cardCoverOverlayBottomRow {
  height: 15%;
  display: flex;
  position: absolute;
  bottom: 0px;
}
.browserLink {
  text-decoration: none;
  color: inherit;
}
.bookCoverProgress {
  margin-top: 1px;
}
.cardSubtitle {
  margin-top: 7px;
  padding-top: 3px;
}
.headerName {
  padding-top: 5px;
  color: gray;
}
.headerName,
.displayName {
  overflow-wrap: break-word;
}
.displayName {
  min-height: 1em;
}
.orderValue {
  color: gray;
}
.metadataButton {
  position: absolute;
  bottom: 5px;
  left: 5px;
}

@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .browserTile {
    margin: 8px;
    width: 100px;
  }
}
</style>
