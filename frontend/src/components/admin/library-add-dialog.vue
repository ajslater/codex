<template>
  <v-dialog
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="30em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn ripple rounded v-on="on"> + Add Library</v-btn>
    </template>
    <v-form id="libraryAddDialog" ref="form">
      <AdminServerFolderPicker
        :rules="pathRules"
        autofocus
        label="Library Folder"
        @keydown.enter="$refs.addLibrary.$el.focus()"
        @change="library.path = $event"
      />
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
        label="Groups"
        :items="vuetifyGroups"
        :value="library.groupSet"
      />

      <v-btn
        ref="addLibrary"
        ripple
        :disabled="!addLibraryButtonEnabled"
        @click="addLibrary"
      >
        Add Library
      </v-btn>
      <v-btn class="addCancelButton" ripple @click="showDialog = false"
        >Cancel</v-btn
      >
      <footer>
        <small v-if="formErrors && formErrors.length > 0" style="color: red">
          <div v-for="error in formErrors" :key="error">
            {{ error }}
          </div>
        </small>
        <small v-else-if="formSuccess" style="color: green"
          >{{ formSuccess }}
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import AdminServerFolderPicker from "@/components/admin/server-folder-picker.vue";
import TimeTextField from "@/components/admin/time-text-field.vue";
import { useAdminStore } from "@/stores/admin";

const EMPTY_LIBRARY = {
  path: "",
  events: true,
  poll: true,
  pollEvery: "01:00:00",
  groupSet: [],
};
Object.freeze(EMPTY_LIBRARY);

export default {
  name: "AdminLibraryAddDialog",
  components: {
    AdminRelationPicker,
    AdminServerFolderPicker,
    TimeTextField,
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
      formErrors: (state) => state.errors,
      formSuccess: (state) => state.success,
      paths: (state) => {
        const libraryPaths = [];
        for (const library of state.libraries) {
          libraryPaths.push(library.path);
        }
        return libraryPaths;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    addLibraryButtonEnabled: function () {
      for (const rule of this.pathRules) {
        if (rule(this.library.path) !== true) {
          return false;
        }
      }
      return true;
    },
  },
  watch: {
    showDialog(show) {
      if (show) {
        this.clearErrors();
        this.loadFolders();
      }
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["clearErrors", "createRow", "loadFolders"]),
    addLibrary: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        return;
      }
      this.createRow("Library", this.library)
        .then(() => {
          this.showDialog = false;
          this.library = { ...EMPTY_LIBRARY };
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
  },
};
</script>

<style scoped lang="scss">
#libraryAddDialog {
  padding: 20px;
}
</style>
