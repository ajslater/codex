<template>
  <v-lazy
    :id="'card-' + item.pk"
    transition="scale-transition"
    class="browserTile"
  >
    <div class="browserTileLazyWrapper">
      <div class="browserCardCoverWrapper" @click="doubleTapHovered = true">
        <BookCover
          :cover-pk="item.coverPk"
          :updated-at="item.coverUpdatedAt"
          :group="item.group"
          :child-count="item.childCount"
          :finished="item.finished"
        />
        <div class="cardCoverOverlay">
          <router-link
            v-if="toRoute"
            class="browserLink"
            :to="toRoute"
            :aria-label="linkLabel"
          >
            <div class="cardCoverOverlayTopMiddleRow">
              <v-icon v-if="item.group === 'c'">
                {{ mdiEye }}
              </v-icon>
            </div>
          </router-link>
          <div v-else class="cardCoverOverlayTopMiddleRow">
            <v-icon v-if="item.group === 'c'">{{ mdiEyeOff }}</v-icon>
          </div>
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
        aria-label="% read"
        rounded
        background-color="inherit"
        height="2"
      />
      <span class="browserLink cardSubtitle text-caption">
        <div v-if="headerName" class="headerName">{{ headerName }}</div>
        <div class="displayName">{{ displayName }}</div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-if="orderValue" class="orderValue" v-html="orderValue" />
      </span>
    </div>
  </v-lazy>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";
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
import { IS_IOS, IS_TOUCH } from "@/platform";
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
      mdiEyeOff,
      doubleTapHovered: !IS_TOUCH || IS_IOS,
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
    toRoute: function () {
      if (!this.doubleTapHovered) {
        return {};
      }
      return this.item.group === "c"
        ? getReaderRoute(this.item)
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
    // can't use computed value.
    this.orderByCache = this.$store.state.browser.settings.orderBy;
  },
  mounted() {
    this.scrollToMe();
  },
  methods: {
    scrollToMe: function () {
      if (
        !this.$route.hash ||
        this.$route.hash.split("-")[1] !== String(this.item.pk)
      ) {
        return;
      }
      const el = this.$el;
      if (!el) {
        console.warn("No element found to scroll to!");
        return;
      }
      setTimeout(
        function () {
          // This works while nextTick() does not.
          el.scrollIntoView();
          // Adjust for toolbars
          const header = document.querySelector("#browserHeader");
          const verticalOffset = (header.offsetHeight + 16) * -1;
          window.scrollBy(0, verticalOffset);
        },
        // A little hacky delay makes it work even more frequently.
        100
      );
    },
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
  height: 85%;
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
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .browserTile {
    margin: 8px;
    width: 100px;
  }
  .cardCoverOverlayTopMiddleRow {
    height: 82%;
  }
  .cardCoverOverlayBottomRow {
    height: 18%;
  }
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
div.cardCoverOverlayBottomRow > * {
  position: absolute;
  bottom: 0px;
}
.metadataButton {
  left: 0px;
}
</style>
