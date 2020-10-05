<template>
  <div id="browser">
    <header id="browserHeader">
      <BrowserFilterToolbar />
      <BrowserTitleToolbar />
    </header>
    <BrowserMain />
    <BrowserFooter />
    <v-snackbar
      id="scanNotify"
      :value="scanNotify"
      bottom
      right
      rounded
      width="183"
      :timeout="-1"
    >
      Scanning Libraries
      <v-progress-circular size="18" indeterminate color="#cc7b19" />
      <v-btn
        id="dismissScanNotify"
        title="dismiss notification"
        x-small
        ripple
        @click="setScanNotify(null)"
        >x</v-btn
      >
    </v-snackbar>
    <v-snackbar
      id="failedImportsNotify"
      :value="failedImportsNotify"
      bottom
      right
      rounded
      width="183"
      :timeout="-1"
    >
      Review failed imports in the
      <a :href="failedImportURL">Admin Panel</a>
      <v-btn
        id="dismissFailedImportsNotify"
        title="dismiss notification"
        x-small
        ripple
        @click="failedImportsNotify = false"
        >x</v-btn
      >
    </v-snackbar>
  </div>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { FAILED_IMPORT_URL, getSocket } from "@/api/v1/browser";
import WS_MESSAGES from "@/choices/websocketMessages.json";
import BrowserFilterToolbar from "@/components/browser-filter-toolbar";
import BrowserFooter from "@/components/browser-footer";
import BrowserMain from "@/components/browser-main";
import BrowserTitleToolbar from "@/components/browser-title-toolbar";

const SCAN_DONE_MSGS = new Set([
  WS_MESSAGES.admin.SCAN_DONE,
  WS_MESSAGES.admin.FAILED_IMPORTS,
]);

export default {
  name: "Browser",
  components: {
    BrowserFilterToolbar,
    BrowserFooter,
    BrowserMain,
    BrowserTitleToolbar,
  },
  data() {
    return {
      socket: undefined,
      failedImportsNotify: false,
      failedImportURL: FAILED_IMPORT_URL,
    };
  },
  computed: {
    ...mapState("browser", {
      scanNotify: (state) => state.scanNotify,
    }),
    ...mapState("auth", {
      user: (state) => state.user,
    }),
    ...mapGetters("auth", ["isAdmin", "isOpenToSee"]),
    outdated: function () {
      return this.versions.latest > this.versions.installed;
    },
  },
  watch: {
    $route(newRoute) {
      this.$store.dispatch("browser/routeChanged", newRoute.params);
    },
    user() {
      this.connectToServer();
      if (this.isAdmin) {
        this.setScanNotify(false);
      }
    },
  },
  created() {
    this.connectToServer();
  },
  beforeDestroy() {
    if (this.socket) {
      this.socket.close();
    }
  },
  methods: {
    connectToServer: function () {
      if (!this.isOpenToSee) {
        if (this.socket) {
          this.socket.close();
        }
        return;
      }
      this.$store.dispatch("browser/browserOpened", this.$route.params);
      this.socket = getSocket(this.isAdmin);
      this.socket.addEventListener("message", this.websocketListener);
    },
    websocketListener: function (event) {
      console.debug("websocket push:", event.data);
      if (event.data === WS_MESSAGES.user.LIBRARY_CHANGED) {
        this.$store.dispatch("browser/getBrowserPage");
      } else if (this.isAdmin) {
        if (event.data === WS_MESSAGES.admin.SCAN_LIBRARY) {
          this.setScanNotify(true);
        } else if (SCAN_DONE_MSGS.has(event.data)) {
          this.setScanNotify(false);
          if (event.data === WS_MESSAGES.admin.FAILED_IMPORTS) {
            this.failedImportsNotify = true;
          }
        }
      }
    },
    setScanNotify: function (value) {
      this.$store.dispatch("browser/scanNotify", value);
    },
  },
};
</script>

<style scoped lang="scss">
#browser {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
#browserHeader {
  position: fixed;
  z-index: 10;
}
#dismissScanNotify {
  margin-left: 5px;
}
#failedImportsNotify a {
  padding-right: 0.5em;
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
#scanNotify > .v-snack__wrapper {
  min-width: 183px;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
