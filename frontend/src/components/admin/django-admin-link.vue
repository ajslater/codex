<template>
  <v-list-item id="oldDjangoAdmin" :href="djangoAdminURL" target="_blank">
    <v-list-item-title>
      Old Admin Panel
      <v-icon size="small">
        {{ mdiOpenInNew }}
      </v-icon>
    </v-list-item-title>
  </v-list-item>
</template>
<script>
import { mdiOpenInNew } from "@mdi/js";
export default {
  name: "DjangoAdminLink",
  data() {
    return {
      djangoAdminURL: window.CODEX.DJANGO_ADMIN_PATH,
      mdiOpenInNew,
    };
  },
};
</script>

<style scoped lang="scss">
#oldDjangoAdmin:hover {
  color: rgb(var(--v-theme-linkHover));
}
#oldDjangoAdmin {
  color: rgb(var(--v-theme-textDisabled));
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#oldDjangoAdmin .v-icon {
  color: rgb(var(--v-theme-textDisabled));
}
#oldDjangoAdmin:hover .v-icon {
  color: rgb(var(--v-theme-linkHover)) !important;
}
</style>
