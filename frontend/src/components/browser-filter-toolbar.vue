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
  padding-top: 6px; /* for filter labels */
  width: 100vw;
}
#filterToolbarItems {
  padding-top: 10px;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.toolbarSelect .v-input__control > .v-input__slot:before {
  border: none;
}
/* ids aren't kept by vuetify for v-select. abuse classes */
.filterMenuHidden > .v-select-list > .v-list-item {
  display: none !important;
}
.v-select.toolbarSelect {
  white-space: nowrap;
  margin-left: 2px;
  margin-right: 2px;
}
.v-select.toolbarSelect .v-select__selection--comma {
  text-overflow: unset;
}
.v-select.filterSelect {
  width: 152px;
  margin-left: 0px;
}
.v-select.rootGroupSelect {
  width: 122px;
}
.v-select.sortBySelect {
  width: 148px;
  margin-right: 0px;
}

@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #filterToolbar > .v-toolbar__content {
    padding-right: 0px;
    padding-left: 0px;
  }
  #filterToolbar .v-select__selection,
  #filterToolbar .v-select__selections {
    font-size: 12px;
  }
  .v-select.toolbarSelect {
    margin-left: 0px;
    margin-right: 0px;
  }

  .v-select.filterSelect {
    width: 128px;
  }
  .v-select.rootGroupSelect {
    width: 100px;
  }
  .v-select.sortBySelect {
    width: 118px;
  }
}
</style>
