<template>
  <v-toolbar id="browserToolbar" class="toolbar" density="compact">
    <v-toolbar-items v-if="isCodexViewable" id="browserToolbarLeftItems">
      <BrowserRootGroupSelect id="topGroupSelect" />
      <BrowserOrderBySelect id="orderBySelect" />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items id="browserToolbarRightItems">
      <SettingsDrawerButton @click="isSettingsDrawerOpen = true" />
    </v-toolbar-items>
    <template #extension>
      <v-toolbar-items v-if="isCodexViewable" id="searchToolbarItems">
        <BrowserFilterSelect id="filterSelect" />
        <BrowserSearchField id="searchField" />
      </v-toolbar-items>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";
import { mapGetters, mapWritableState } from "pinia";

import BrowserFilterSelect from "@/components/browser/filter-select.vue";
import BrowserOrderBySelect from "@/components/browser/order-by-select.vue";
import BrowserSearchField from "@/components/browser/search-field.vue";
import BrowserRootGroupSelect from "@/components/browser/top-group-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserHeader",
  components: {
    BrowserFilterSelect,
    BrowserRootGroupSelect,
    BrowserSearchField,
    BrowserOrderBySelect,
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
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useBrowserStore, ["isSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#browserToolbar {
  padding-top: calc(6px + env(safe-area-inset-top)); /* for filter labels */
  width: 100vw;
}
#browserToolbarLeftItems {
  padding-top: 10px;
  padding-left: calc(env(safe-area-inset-left) / 3);
}
#browserToolbarRightItems {
  padding-right: calc(env(safe-area-inset-right) / 3);
}

#topGroupSelect {
  margin-left: 22px;
  width: 130px;
}
#orderBySelect {
  margin-left: 16px;
  width: 188px;
  margin-right: 0px;
}
#filterSelect {
  max-width: 152px;
  margin-left: 0px;
  padding-left: 0px;
  margin-right: 1px;
  /* Fake solo styling */
  padding-top: 8px;
  background-color: rgb(var(--theme-surface));
  border-radius: 4px;
  max-height: 40px;
}
#searchToolbarItems {
  width: 100%;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #browserToolbar {
    padding-left: 4px;
    padding-right: 4px;
  }
  #topGroupSelect {
    width: 136px;
    padding-left: 2px;
  }
  #orderBySelect {
    margin-left: 2px;
  }
  #filterSelect {
    width: 172px;
  }
  #searchField {
    margin-right: 0px;
  }
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#browserToolbar .toolbarSelect {
  white-space: nowrap !important;
}
#browserToolbar .toolbarSelect .v-select__selection--comma {
  text-overflow: unset !important;
}
#browserToolbar .toolbarSelect .v-input__control > .v-input__slot:before {
  border: none !important;
}
#orderBySelect .v-select__selection--comma {
  margin-right: 0px !important;
  max-width: 100% !important;
}
#orderBySelect .v-select__selections input {
  display: none;
}
#orderBySelect .v-select.v-input--dense .v-select__selection--comma {
  margin-right: 0px !important;
}
#orderBySelect .v-input__append-inner {
  padding: 0px !important;
}
#filterSelect .v-input__prepend-inner {
  padding-right: 0px !important;
}
#filterSelect .v-input__icon--prepend-inner svg {
  color: rbg(var(--v-theme-iconsInactive)) !important;
  width: 16px !important;
}
#filterSelect .v-label {
  /* Counteract fake solo styling */
  top: -6px !important;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #browserToolbar .v-toolbar__content,
  #browserToolbar .v-toolbar__extension {
    padding-right: 0px !important;
    padding-left: 0px !important;
  }
  #browserToolbar .toolbarSelect {
    margin-left: 0px !important;
    margin-right: 0px !important;
  }
}
</style>
