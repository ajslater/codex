<template>
  <div>
    <AuthMenu />
    <AdminMenu />

    <v-divider />
    <div id="opds">
      <h3>OPDS</h3>
      {{ opdsURL }}
    </div>
    <VersionsFooter />
  </div>
</template>

<script>
import AdminMenu from "@/components/admin/menu.vue";
import AuthMenu from "@/components/auth/menu.vue";
import VersionsFooter from "@/components/settings/version-footer.vue";

export default {
  name: "SettingsCommonPanel",

  components: {
    AuthMenu,
    VersionsFooter,
    AdminMenu,
  },
  data() {
    return {
      // Could calculate this server side, but whatever
      opdsURL: window.origin + window.CODEX.OPDS_PATH,
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
  font-size: smaller;
  overflow-wrap: anywhere;
  color: grey;
}
</style>
