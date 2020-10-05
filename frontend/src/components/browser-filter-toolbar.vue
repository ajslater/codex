<template>
  <v-toolbar id="filterToolbar" class="toolbar" dense>
    <v-toolbar-items v-if="isOpenToSee" id="filterToolbarItems">
      <BrowserFilterSelect />
      <BrowserRootGroupSelect />
      <BrowserSortBySelect />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items id="controls">
      <BrowserSettingsMenu />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapGetters } from "vuex";

import BrowserFilterSelect from "@/components/browser-filter-select";
import BrowserRootGroupSelect from "@/components/browser-root-group-select";
import BrowserSettingsMenu from "@/components/browser-settings-menu";
import BrowserSortBySelect from "@/components/browser-sort-by-select";

export default {
  name: "BrowserHeader",
  components: {
    BrowserFilterSelect,
    BrowserRootGroupSelect,
    BrowserSettingsMenu,
    BrowserSortBySelect,
  },
  data() {
    return {
      mdiDotsVertical,
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
  },
};
</script>

<style scoped lang="scss">
#filterToolbar {
  width: 100vw;
}
#filterToolbarItems {
  padding-top: 8px;
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
#filterToolbar > .v-toolbar__content {
  padding-right: 0px;
}
#filterToolbar .filterSelect .v-input__prepend-inner {
  padding-right: 0px;
}
#filterToolbar .filterSelect .v-input__prepend-inner .v-input__icon > .v-icon {
  margin-top: 1px;
}
#filterToolbar .filterSelect .v-input__icon--prepend-inner svg {
  width: 16px;
}
.toolbarSelect {
  padding-top: 3px;
}
.toolbarSelect .v-input__slot {
  border: none;
}
.toolbarSelect .v-input__append-inner {
  padding-left: 0px !important;
}
.toolbarSelect .v-input__control > .v-input__slot:before {
  border: none;
}
/* ids aren't kept by vuetify for v-select. abuse classes */
.filterSelect {
  width: 144px;
}
.filterMenuHidden > .v-select-list > .v-list-item {
  display: none !important;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .toolbarSelect {
    font-size: 12px;
  }
  /* ids aren't kept by vuetify for v-select. abuse classes */
  .filterSelect {
    width: 120px;
  }
  .filterSelect .v-input__icon--prepend-inner svg {
    width: 13px;
  }
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
