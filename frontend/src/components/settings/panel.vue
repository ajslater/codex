<template>
  <div>
    <AuthMenu />
    <component :is="adminMenuLoader" />
    <v-divider />
    <v-list-item-group>
      <v-list-item id="opds" ripple @click="copyToClipboard">
        <v-list-item-content>
          <h3>
            OPDS
            <v-icon small>
              {{ mdiContentCopy }}
            </v-icon>
            <v-fade-transition>
              <span v-if="showTool" id="copied"> Copied </span>
            </v-fade-transition>
          </h3>
          {{ opdsURL }}
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
    <VersionsFooter />
  </div>
</template>

<script>
import { mdiContentCopy } from "@mdi/js";
import { mapGetters } from "pinia";

import { useAuthStore } from "@/stores/auth";

const AdminMenu = () => import("@/components/admin/menu.vue");
import AuthMenu from "@/components/auth/menu.vue";
import VersionsFooter from "@/components/settings/version-footer.vue";

export default {
  name: "SettingsCommonPanel",
  components: {
    AuthMenu,
    VersionsFooter,
  },
  data() {
    return {
      // Could calculate this server side, but whatever
      opdsURL: window.origin + window.CODEX.OPDS_PATH,
      mdiContentCopy,
      showTool: false,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    adminMenuLoader: function () {
      return this.isUserAdmin ? AdminMenu : undefined;
    },
  },
  methods: {
    copyToClipboard() {
      navigator.clipboard
        .writeText(this.opdsURL)
        .then(() => {
          this.showTool = true;
          setTimeout(() => {
            this.showTool = false;
          }, 5000);
          return true;
        })
        .catch((error) => {
          console.warn(error);
        });
    },
  },
};
</script>

<style scoped lang="scss">
#opds {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: calc(env(safe-area-inset-right) + 10px);
  padding-bottom: 10px;
  font-size: smaller;
  overflow-wrap: anywhere;
  color: grey;
}
#copied {
  color: white;
  padding-left: 0.5em;
}

/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
#opds .v-icon {
  color: grey;
}
/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
#opds:hover .v-icon {
  color: white;
}
</style>
