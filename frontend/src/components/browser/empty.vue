<template>
  <EmptyState
    class="browserEmpty"
    :headline="empty.headline"
    :title="empty.title"
    :icon="empty.icon"
    :action-text="actionText"
    @click:action="clearFilters(true)"
  >
    <div v-if="showLinkToReadmeAdmin">
      See the
      <a
        href="https://github.com/ajslater/codex#-administration"
        target="_blank"
        >README <v-icon>{{ mdiOpenInNew }}</v-icon></a
      >
      for help
    </div>
  </EmptyState>
</template>

<script>
import {
  mdiBookSearchOutline,
  mdiOpenInNew,
  mdiShieldCrownOutline,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import EmptyState from "@/components/empty.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserEmptyResults",
  components: {
    EmptyState,
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthorized", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      registration: (state) => state.adminFlags.registration,
    }),
    ...mapState(useBrowserStore, ["isFiltersClearable"]),
    ...mapState(useBrowserStore, {
      librariesExist: (state) => state.page.librariesExist,
    }),
    empty() {
      let res = {};
      if (this.librariesExist) {
        res.headline = "No Comics Found";
        res.title = "For these filter and search settings";
        res.icon = mdiBookSearchOutline;
      } else {
        res.headline = "No Libraries Exist";
        if (this.isUserAdmin) {
          res.title =
            "Use the top right ☰ menu to navigate to the admin panel and add a comic library";
        } else if (this.isAuthorized) {
          res.title = "An administrator must add some comics libraries";
        } else {
          res.title =
            "Use the top right ☰ menu to log in as an administrator to add libraries";
        }
        res.icon = mdiShieldCrownOutline;
      }

      return res;
    },
    showLinkToReadmeAdmin() {
      return !this.librariesExist && this.isUserAdmin;
    },
    actionText() {
      return this.isFiltersClearable ? "Clear Filters and Search" : "";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["clearFilters"]),
  },
};
</script>
