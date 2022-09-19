<template>
  <v-simple-table fixed-header :height="tableHeight">
    <template #default>
      <thead>
        <tr>
          <th>Name</th>
          <th>Enabled</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in flags" :key="`f:${item.id}:${item.keyHack}`">
          <td class="nameCol">
            {{ item.name }}
          </td>
          <td>
            <v-checkbox
              :input-value="item.on"
              dense
              ripple
              hide-details="auto"
              :error-messages="getFormErrors(item.id, 'on')"
              @focus="clearErrors"
              @blur="item.keyHack = Date.now()"
              @change="changeCol(item.id, 'on', $event === true)"
            />
          </td>
          <td class="descCol">
            {{ DESC[item.name] }}
          </td>
        </tr>
      </tbody>
    </template>
  </v-simple-table>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

const DESC = {
  "Enable Auto Update":
    "If enabled, codex will attempt to update the codex python package once a day and restart the server if an update occurred. Not advisable if running from Docker as running containers aren't meant to hold state and will be rebuilt if you update the image. Look into services that automatically update docker images instead.",
  "Enable Non Users":
    "By default all Codex features, including bookmarking, are available to users who are not logged in. You may disable this feature and Codex will hide its browser and reader and disable its API from anyone who is not logged in as a user.",
  "Enable Registration":
    "By default users' bookmarks and preferences are saved in an anonymous browser session. Users can create a username and password to save their bookmarks between browsers. You may disable this feature. Admins may still create users.",
  "Enable Folder View":
    'By default, codex provides a "Folder View" which mimics the directory hierarchy of the libraries that you\'ve added to Codex. You may disable this feature. The database style browser view is always available. This flag also enables and disables the "Filename" sort option.',
};
Object.freeze(DESC);

export default {
  name: "AdminFlagsPanel",
  data() {
    return {
      lastUpdate: {
        pk: 0,
        field: undefined,
      },
      DESC,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      flags: (state) => state.flags,
    }),
    tableHeight: () => window.innerHeight * 0.9,
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors"]),
    changeCol(pk, field, val) {
      this.lastUpdate.pk = pk;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Flag", pk, data);
    },
    getFormErrors(pk, field) {
      if (pk === this.lastUpdate.pk && field === this.lastUpdate.field) {
        return this.formErrors;
      }
    },
  },
};
</script>

<style scoped lang="scss">
.nameCol {
  min-width: 12em;
}
.descCol {
  color: lightgrey;
  min-width: 15em;
}
</style>
