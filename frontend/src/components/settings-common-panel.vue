<template>
  <div>
    <AuthLoginDialog />
    <AdminMenu />

    <v-divider />
    <div id="opds">
      <h3>OPDS</h3>
      <a :href="opdsURL">{{ opdsURL }}</a>
    </div>
    <VersionsFooter />
  </div>
</template>

<script>
import AdminMenu from "@/components/admin-menu";
import AuthLoginDialog from "@/components/auth-login-dialog";
import VersionsFooter from "@/components/version-footer";

export default {
  name: "SettingsCommonPanel",

  components: {
    AuthLoginDialog,
    VersionsFooter,
    AdminMenu,
  },
  data() {
    return {
      // Could calculate this server side, but whatever
      opdsURL: window.origin + window.CODEX.ROOT_PATH + "opds/v1.2/r/0/1",
    };
  },
};
</script>

<style scoped lang="scss">
#opds {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: calc(env(safe-area-inset-right) + 10px);
  padding-bottom: 10px;
}
#opds a {
  font-size: smaller;
  overflow-wrap: anywhere;
}
</style>
