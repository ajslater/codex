<template>
  <v-empty-state
    class="empty"
    headline="Unauthorized"
    :title="empty.title"
    :text="empty.text"
    :icon="empty.icon"
    @click="isSettingsDrawerOpen = true"
  />
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapGetters, mapState, mapWritableState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "UnauthorizedEmptyState",
  props: {
    admin: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable", "isUserAdmin"]),
    ...mapState(useAuthStore, {
      registration: (state) => state.adminFlags.registration,
      user: (state) => state.user,
    }),
    ...mapWritableState(useCommonStore, ["isSettingsDrawerOpen"]),
    empty() {
      const res = {
        headline: "Unauthorized",
        icon: mdiLogin,
      };
      res.title = "Log in ";
      if (this.registration) {
        res.title += "or register ";
      }
      if (this.admin && !this.isUserAdmin) {
        res.title += "as an administrator ";
      }
      res.title += "to view this page";
      if (!this.registration) {
        res.text = "Registration is disabled";
      } else {
        res.text = "";
      }
      return res;
    },
  },
  watch: {
    isSettingsDrawerOpen(value) {
      // Hack the drawer permanently open.
      if (!value) {
        this.isSettingsDrawerOpen = true;
      }
    },
  },
  mounted() {
    this.isSettingsDrawerOpen = true;
  },
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
