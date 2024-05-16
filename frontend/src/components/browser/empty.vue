<template>
  <v-empty-state
    class="empty"
    :headline="empty.headline"
    :title="empty.title"
    :icon="empty.icon"
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
    <v-btn
      v-if="isFiltersClearable"
      class="clearFilter"
      @click="clearFilters(true)"
    >
      Clear Filters and Search<v-icon :icon="mdiCloseCircleOutline" />
    </v-btn>
  </v-empty-state>
</template>

<script>
import {
  mdiBookSearchOutline,
  mdiCloseCircleOutline,
  mdiOpenInNew,
  mdiShieldCrownOutline,
} from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "EmptyState",
  data() {
    return {
      mdiOpenInNew,
      mdiCloseCircleOutline,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isAuthorized", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      registration: (state) => state.adminFlags.registration,
    }),
    ...mapGetters(useBrowserStore, ["isFiltersClearable"]),
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
        } else {
          res.title = "An administrator must add some comics libraries";
        }
        res.icon = mdiShieldCrownOutline;
      }

      return res;
    },
    showLinkToReadmeAdmin() {
      return !this.librariesExist && this.isUserAdmin;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["clearFilters"]),
  },
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
.clearFilter {
  color: black;
  background-color: rgb(var(--v-theme-primary))
}
</style>
