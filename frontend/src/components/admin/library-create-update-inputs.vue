<template>
  <div id="libraryInputs" :class="{ tallForPicker: folderMenuOpen }">
    <AdminServerFolderPicker
      v-if="!oldRow"
      :rules="rules.path"
      autofocus
      label="Library Folder"
      @change="row.path = $event"
      @menu="folderMenuOpen = folderMenuOpen || $event"
    />
    <div v-else>{{ oldRow.path }}</div>
    <v-checkbox
      v-model="row.events"
      label="Watch Filesystem Events"
      ripple
      hint="Update Codex instantly when the filesystem changes"
      :persistent-hint="true"
    />
    <v-checkbox
      v-model="row.poll"
      label="Poll Filesystem"
      ripple
      hint="Periodically poll the library for changes"
      :persistent-hint="true"
    />
    <TimeTextField
      v-model="row.pollEvery"
      label="Poll Every"
      :disabled="!row.poll"
    />
    <AdminRelationPicker
      v-model="row.groups"
      label="Groups"
      :items="vuetifyGroups"
    />
  </div>
</template>

<script>
import _ from "lodash";
import { mapActions, mapGetters, mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import AdminServerFolderPicker from "@/components/admin/server-folder-picker.vue";
import TimeTextField from "@/components/admin/time-text-field.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["events", "poll", "pollEvery", "groups"];
Object.freeze(UPDATE_KEYS);
const EMPTY_ROW = {
  path: "",
  events: true,
  poll: true,
  pollEvery: "01:00:00",
  groups: [],
};
Object.freeze(EMPTY_ROW);

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminLibraryCreateUpdateInputs",
  components: {
    AdminRelationPicker,
    AdminServerFolderPicker,
    TimeTextField,
  },
  props: {
    oldRow: {
      type: [Object, Boolean],
      default: false,
    },
  },
  emits: ["change"],
  data() {
    return {
      rules: {
        path: [
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
      },
      row: _.cloneDeep(this.oldRow || EMPTY_ROW),
      folderMenuOpen: false,
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    ...mapState(useAdminStore, {
      libraries: (state) => state.libraries,
    }),
    paths() {
      return this.nameSet(this.libraries, "path", this.oldRow, false);
    },
  },
  watch: {
    row: {
      handler(to) {
        this.$emit("change", to);
      },
      deep: true,
    },
    oldRow: {
      handler(to) {
        this.row = _.cloneDeep(to);
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["nameSet"]),
  },
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>

<style scoped lang="scss">
.tallForPicker {
  height: 75vh;
}
#libraryInputs {
  transition: height 0.33s;
}
</style>
