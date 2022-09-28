<template>
  <v-list-item-group>
    <v-list-item
      id="oldDjangoAdmin"
      :href="djangoAdminURL"
      target="_blank"
      ripple
    >
      <v-list-item-content>
        <v-list-item-title>
          Old Admin Panel
          <v-icon small>
            {{ mdiOpenInNew }}
          </v-icon>
        </v-list-item-title>
      </v-list-item-content>
    </v-list-item>
  </v-list-item-group>
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
  color: white;
}
#oldDjangoAdmin {
  color: grey;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#oldDjangoAdmin .v-icon {
  color: grey;
}
#oldDjangoAdmin:hover .v-icon {
  color: white;
}
</style>
