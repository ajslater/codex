<template>
  <div v-if="isAdmin">
    <h3 id="adminMenuTitle">Admin Tools</h3>
    <v-list-item-group>
      <v-list-item ripple @click="poll">
        <v-list-item-content>
          <v-list-item-title>Poll All Libraries</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
      <v-list-item :href="adminURL" target="_blank" ripple>
        <v-list-item-content>
          <v-list-item-title
            >Admin Panel
            <v-icon id="adminPanelIcon">{{
              mdiOpenInNew
            }}</v-icon></v-list-item-title
          >
        </v-list-item-content>
      </v-list-item>
    </v-list-item-group>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapGetters } from "vuex";

import API from "@/api/v2/admin";

export default {
  name: "AdminMenu",
  data() {
    return {
      adminURL: API.ADMIN_URL,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters("auth", ["isAdmin"]),
  },
  methods: {
    poll: function () {
      API.queueJob("poll");
    },
  },
};
</script>

<style scoped lang="scss">
#adminMenuTitle {
  padding-left: 15px;
}
#adminPanelIcon {
  color: gray;
}
</style>
