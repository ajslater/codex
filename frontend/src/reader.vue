<template>
  <v-main v-if="isAuthorized" id="readerWrapper">
    <div v-if="!empty">
      <div id="readerContainer">
        <ReaderTopToolbar />
        <BooksWindow />
        <ReaderNavToolbar />
      </div>
    </div>
    <ReaderEmpty v-else />
    <ReaderSettingsDrawer />
  </v-main>
  <Unauthorized v-else />
</template>

<script>
import { mapActions, mapState } from "pinia";

import BooksWindow from "@/components/reader/books-window.vue";
import ReaderSettingsDrawer from "@/components/reader/drawer/reader-settings-drawer.vue";
import ReaderEmpty from "@/components/reader/empty.vue";
import ReaderNavToolbar from "@/components/reader/toolbars/nav/reader-toolbar-nav.vue";
import ReaderTopToolbar from "@/components/reader/toolbars/top/reader-toolbar-top.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "MainReader",
  components: {
    BooksWindow,
    ReaderEmpty,
    ReaderNavToolbar,
    ReaderTopToolbar,
    ReaderSettingsDrawer,
    Unauthorized,
  },
  data() {
    return {
      showToolbars: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthorized"]),
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapState(useReaderStore, {
      empty: (state) => state.empty,
    }),
  },
  watch: {
    user() {
      this.loadReaderSettings();
    },
  },
  created() {
    // useReaderStore().$reset; // Not working
    this.reset(); // HACK
    const wait = this.user ? 0 : 300;
    const createdUser = this.user;
    setTimeout(() => {
      if (this.user?.id === createdUser?.id) {
        this.loadReaderSettings();
      }
    }, wait);
  },
  methods: {
    ...mapActions(useReaderStore, ["loadReaderSettings", "reset"]),
  },
};
</script>

<style scoped lang="scss">
#readerContainer {
  max-width: 100%;
  position: relative;
}
</style>
