<template>
  <v-empty-state
    class="empty"
    :headline="empty.headline"
    :title="empty.title"
    :text="empty.text"
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
  </v-empty-state>
</template>

<script>
import {
  mdiBookSearchOutline,
  mdiLogin,
  mdiOpenInNew,
  mdiShieldCrownOutline,
} from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserEmpty",
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      registration: (state) => state.adminFlags.registration,
    }),
    ...mapState(useBrowserStore, {
      librariesExist: (state) => state.page.librariesExist,
    }),
    empty() {
      let res = {};
      if (!this.isCodexViewable) {
        res.headline = "Unauthorized";
        res.title = "You may log in ";
        if (this.registration) {
          res.title += "or register ";
        }
        res.title += "with the top right ☰ menu";
        if (this.registration) {
          res.text = "";
        } else {
          res.text = "Registration is disabled";
        }
        res.icon = mdiLogin;
      } else if (this.librariesExist) {
        res.headline = "No Comics Found";
        res.title = "For these filter and search settings";
        res.text = "";
        res.icon = mdiBookSearchOutline;
      } else {
        res.headline = "No Libraries Exist";
        if (this.isUserAdmin) {
          res.title =
            "Use the top right ☰ menu to navigate to the admin panel and add a comic library";
        } else {
          res.title = "An administrator must add some comics libraries";
        }
        res.text = "";

        res.icon = mdiShieldCrownOutline;
      }

      return res;
    },
    showLinkToReadmeAdmin() {
      return !this.librariesExist && this.isUserAdmin;
    },
  },
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
