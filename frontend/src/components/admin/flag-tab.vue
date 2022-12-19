<template>
  <v-table fixed-header :height="tableHeight" class="highlight-table admin-tab">
    <template #default>
      <thead>
        <tr>
          <th>Description</th>
          <th>Enabled</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in flags" :key="`f${item.pk}`">
          <td class="nameCol">
            <h4>{{ item.name }}</h4>
            <p class="desc">
              {{ DESC[item.name] }}
            </p>
          </td>
          <td>
            <v-checkbox
              :model-value="item.on"
              :true-value="true"
              :error-messages="getFormErrors(item.pk, 'on')"
              hide-details="auto"
              @update:model-value="changeCol(item.pk, 'on', $event)"
            />
          </td>
        </tr>
      </tbody>
    </template>
  </v-table>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

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

const FIXED_TOOLBARS = 96 + 16;
const TABLE_PADDING = 24;
const BUFFER = FIXED_TOOLBARS + TABLE_PADDING;

export default {
  name: "AdminFlagsTab",
  props: {
    innerHeight: {
      type: Number,
      required: true,
    },
  },
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
    ...mapState(useCommonStore, ["formErrors"]),
    ...mapState(useAdminStore, ["flags"]),
    tableHeight() {
      return this.innerHeight - BUFFER;
    },
  },
  mounted() {
    this.loadTables(["Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "loadTables"]),
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
  padding-top: 0.5em !important;
}
.desc {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
