<template>
  <v-empty-state
    class="empty"
    headline="Unauthorized"
    :title="empty.title"
    :text="empty.text"
    :icon="empty.icon"
  />
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapGetters, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

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
    }),
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
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
