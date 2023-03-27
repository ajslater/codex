<template>
  <v-table class="highlight-table flags-table" :items="flags" fixed-header>
    <thead>
      <tr>
        <th>Description</th>
        <th>Enabled</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in flags" :key="`f${item.key}`">
        <td class="nameCol">
          <h4>{{ title(item) }}</h4>
          <p class="desc">
            {{ DESC[item.key] }}
          </p>
        </td>
        <td>
          <v-checkbox
            :model-value="item.on"
            :true-value="true"
            :error-messages="getFormErrors(item.key, 'on')"
            hide-details="auto"
            @update:model-value="changeCol(item.key, 'on', $event)"
          />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { adminFlags } from "@/choices-admin";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const DESC = {
  AU: "If enabled, codex will attempt to update the codex python package once a day and restart the server if an update occurred. Not advisable if running from Docker as running containers aren't meant to hold state and will be rebuilt if you update the image. Look into services that automatically update docker images instead.",
  NU: "By default all Codex features, including bookmarking, are available to users who are not logged in. You may disable this feature and Codex will hide its browser and reader and disable its API from anyone who is not logged in as a user.",
  RG: "By default users' bookmarks and preferences are saved in an anonymous browser session. Users can create a username and password to save their bookmarks between browsers. You may disable this feature. Admins may still create users.",
  FV: 'By default, codex provides a "Folder View" which mimics the directory hierarchy of the libraries that you\'ve added to Codex. You may disable this feature. The database style browser view is always available. This flag also enables and disables the "Filename" sort option.',
  SO: "Fully optimize the search index each night. Disabling this flag will instead run a partial optimization which only merges small files. You should only disable this if the nightly optimization stresses your system too much.",
};
Object.freeze(DESC);

export default {
  name: "AdminFlagsTab",
  components: {},
  data() {
    return {
      lastUpdate: {
        name: "",
        field: undefined,
      },
      DESC,
    };
  },
  computed: {
    ...mapState(useCommonStore, ["formErrors"]),
    ...mapState(useAdminStore, ["flags"]),
  },
  mounted() {
    this.loadTables(["Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "loadTables"]),
    changeCol(name, field, val) {
      this.lastUpdate.name = name;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Flag", name, data);
    },
    getFormErrors(name, field) {
      if (name === this.lastUpdate.name && field === this.lastUpdate.field) {
        return this.formErrors;
      }
    },
    title(item) {
      return adminFlags[item.key];
    },
  },
};
</script>

<style scoped lang="scss">
.flags-table {
  max-width: 100vw !important;
  margin-bottom: 24px;
}
:deep(.tableCheckbox) {
  height: 40px;
}
.nameCol {
  padding-top: 0.5em !important;
}
.desc {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
