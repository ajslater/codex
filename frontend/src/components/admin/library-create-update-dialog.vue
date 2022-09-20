<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    max-width="30em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <AdminCreateUpdateButton :update="update" table="Library" v-on="on" />
    </template>
    <v-form ref="form" class="cuForm">
      <AdminServerFolderPicker
        v-if="!update"
        :rules="pathRules"
        autofocus
        label="Library Folder"
        @change="library.path = $event"
      />
      <div v-else>{{ oldLibrary.path }}</div>
      <v-checkbox
        v-model="library.events"
        label="Watch Filesystem Events"
        ripple
        hint="Update Codex instantly when the filesystem changes"
        :persistent-hint="true"
      />
      <v-checkbox
        v-model="library.poll"
        label="Poll Filesystem"
        ripple
        hint="Periodically poll the library for changes"
        :persistent-hint="true"
      />
      <TimeTextField
        v-model="library.pollEvery"
        label="Poll Every"
        :disabled="!library.poll"
      />
      <AdminRelationPicker
        v-model="library.groups"
        label="Groups"
        :items="vuetifyGroups"
      />
      <AdminCreateUpdateFooter
        :update="update"
        table="Library"
        :disabled="submitButtonDisabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminCreateUpdateButton from "@/components/admin/create-update-button.vue";
import AdminCreateUpdateFooter from "@/components/admin/create-update-footer.vue";
import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import AdminServerFolderPicker from "@/components/admin/server-folder-picker.vue";
import TimeTextField from "@/components/admin/time-text-field.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["events", "poll", "pollEvery", "groups"];
const EMPTY_LIBRARY = {
  path: "",
  events: true,
  poll: true,
  pollEvery: "01:00:00",
  groups: [],
};
Object.freeze(EMPTY_LIBRARY);

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminLibraryCreateUpdateDialog",
  components: {
    AdminCreateUpdateButton,
    AdminCreateUpdateFooter,
    AdminRelationPicker,
    AdminServerFolderPicker,
    TimeTextField,
  },
  props: {
    update: { type: Boolean, default: false },
    oldLibrary: {
      type: Object,
      default: () => {
        return { ...EMPTY_LIBRARY };
      },
    },
  },
  data() {
    return {
      pathRules: [
        (v) => !!v || "Path is required",
        (v) => {
          if (!v) {
            return false;
          }
          for (const path of this.paths) {
            if (v.startsWith(path)) {
              return "Path is a child of an existing library";
            }
            if (path.startsWith(v)) {
              return "Path is a parent of an existing library";
            }
          }
          return true;
        },
      ],
      library: { ...EMPTY_LIBRARY },
      showDialog: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      paths: (state) => {
        const paths = new Set();
        for (const library of state.libraries) {
          paths.add(library.path);
        }
        return paths;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    submitButtonDisabled: function () {
      let changed = false;
      for (const [key, value] of Object.entries(this.library)) {
        if (this.oldLibrary[key] !== value) {
          changed = true;
          break;
        }
      }
      if (!changed) {
        return true;
      }
      const form = this.$refs.form;
      return !form || !form.validate();
    },
  },
  watch: {
    showDialog(show) {
      this.clearErrors();
      this.library =
        show && this.update ? this.createUpdateLibrary() : { ...EMPTY_LIBRARY };
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["clearErrors", "createRow", "updateRow"]),
    createUpdateLibrary() {
      const updateLibrary = {};
      for (const key of UPDATE_KEYS) {
        updateLibrary[key] = this.oldLibrary[key];
      }
      return updateLibrary;
    },
    doUpdate: function () {
      // only pass diff from old library as update
      const updateLibrary = {};
      for (const [key, value] of Object.entries(this.library)) {
        if (this.oldLibrary[key] !== value) {
          updateLibrary[key] = value;
        }
      }
      this.updateRow("Library", this.oldLibrary.id, updateLibrary)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    doCreate: function () {
      this.createRow("Library", this.library)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    submit: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        console.warn("submit attempted with invalid form");
        return;
      }
      if (this.update) {
        this.doUpdate();
      } else {
        this.doCreate();
      }
    },
  },
};
</script>

<style scoped lang="scss">
.cuForm {
  padding: 20px;
}
</style>
