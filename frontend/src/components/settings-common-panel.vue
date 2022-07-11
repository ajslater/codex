<template>
  <div>
    <v-divider />
    <AdminMenu />
    <v-divider />
    <AuthLoginDialog />
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
};
</script>
