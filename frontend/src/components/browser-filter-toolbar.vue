<template>
  <v-toolbar id="browserToolbar" class="toolbar" dense>
    <v-toolbar-items v-if="isOpenToSee" id="browserToolbarItems">
      <BrowserRootGroupSelect id="topGroupSelect" />
      <BrowserSortBySelect id="orderBySelect" />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items>
      <SettingsDrawerButton />
    </v-toolbar-items>
    <template #extension>
      <v-toolbar-items v-if="isOpenToSee" id="searchToolbarItems">
        <BrowserFilterSelect id="filterSelect" />
        <BrowserSearchField id="searchField" />
      </v-toolbar-items>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";
import { mapGetters } from "vuex";

import BrowserFilterSelect from "@/components/browser-filter-select";
import BrowserSortBySelect from "@/components/browser-order-by-select";
import BrowserSearchField from "@/components/browser-search-field";
import BrowserRootGroupSelect from "@/components/browser-top-group-select";
import SettingsDrawerButton from "@/components/settings-drawer-button";

export default {
  name: "BrowserHeader",
  components: {
    BrowserFilterSelect,
    BrowserRootGroupSelect,
    BrowserSearchField,
    BrowserSortBySelect,
    SettingsDrawerButton,
  },
  data() {
    return {
      mdiMagnify,
      mdiFamilyTree,
      browseMode: "filter",
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
  },
};
</script>

<style scoped lang="scss">
#browserToolbar {
  padding-top: 6px; /* for filter labels */
  width: 100vw;
}
#browserToolbarItems {
  padding-top: 10px;
  padding-left: 0px;
}

#topGroupSelect {
  margin-left: 18px;
  width: 122px;
}
#orderBySelect {
  margin-left: 16px;
  width: 180px;
  margin-right: 0px;
}
#filterSelect {
  max-width: 152px;
  margin-left: 0px;
  padding-left: 0px;
  margin-right: 1px;
  /* Fake solo styling */
  padding-top: 8px;
  background-color: #1e1e1e;
  border-radius: 4px;
  max-height: 40px;
}
#searchToolbarItems {
  width: 100%;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #topGroupSelect {
    margin-left: 16px;
    width: 136px;
  }
  #orderBySelect {
    margin-left: 2px;
  }
  #filterSelect {
    width: 164px;
  }
  #searchField {
    margin-right: 0px;
  }
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.toolbarSelect {
  white-space: nowrap;
}
.toolbarSelect .v-select__selection--comma {
  text-overflow: unset;
}
.toolbarSelect .v-input__control > .v-input__slot:before {
  border: none;
}
#filterSelect .v-input__prepend-inner {
  padding-right: 0px;
}
#filterSelect .v-input__icon--prepend-inner svg {
  color: gray;
  width: 16px;
}
#filterSelect .v-label {
  /* Counteract fake solo styling */
  top: -6px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #browserToolbar > .v-toolbar__content,
  #browserToolbar > .v-toolbar__extension {
    padding-right: 2px !important;
    padding-left: 0px !important;
  }
  .toolbarSelect {
    margin-left: 0px;
    margin-right: 0px;
  }
}
</style>
