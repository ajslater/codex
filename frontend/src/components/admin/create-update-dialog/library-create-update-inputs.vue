<template>
  <section>
    <AdminServerFolderPicker
      v-if="!oldRow"
      :rules="rules.path"
      autofocus
      label="Library Folder"
      @change="row.path = $event"
    />
    <div v-else>
      {{ oldRow.path }}
    </div>
    <v-checkbox
      v-model="row.events"
      hide-details="auto"
      hint="Update Codex instantly when the filesystem changes"
      label="Watch Filesystem Events"
      :persistent-hint="true"
    />
    <v-checkbox
      v-model="row.poll"
      label="Poll Filesystem Periodically"
      hide-details="auto"
      hint="Periodically poll the library for changes"
      :persistent-hint="true"
    />
    <DurationInput
      v-model="row.pollEvery"
      label="Poll Every"
      :disabled="!row.poll"
    />
    <AdminRelationPicker
      v-if="!row.coversOnly"
      v-model="row.groups"
      label="Groups"
      :objs="groups"
      group-type
      title-key="name"
    />
  </section>
</template>

<script>
import { mapActions, mapState } from "pinia";

import DurationInput from "@/components/admin/create-update-dialog/duration-input.vue";
import AdminRelationPicker from "@/components/admin/create-update-dialog/relation-picker.vue";
import AdminServerFolderPicker from "@/components/admin/create-update-dialog/server-folder-picker.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = Object.freeze(["events", "poll", "pollEvery", "groups"]);
const EMPTY_ROW = Object.freeze({
  path: "",
  events: true,
  poll: true,
  pollEvery: "01:00:00",
  groups: [],
});

const isPathParent = (path, potentialChildPath) => {
  // Normalize the paths to avoid issues with different directory separator characters
  path = path.replaceAll("\\", "/");
  potentialChildPath = potentialChildPath.replaceAll("\\", "/");

  // Ensure that both paths end with a slash to avoid false positives
  if (!path.endsWith("/")) {
    path += "/";
  }
  if (!potentialChildPath.endsWith("/")) {
    potentialChildPath += "/";
  }

  // Check if the potential child path starts with the parent path
  return potentialChildPath.startsWith(path);
};

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminLibraryCreateUpdateInputs",
  components: {
    AdminRelationPicker,
    AdminServerFolderPicker,
    DurationInput,
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
              if (isPathParent(path, v)) {
                return "Path is a child of an existing library";
              }
              if (isPathParent(v, path)) {
                return "Path is a parent of an existing library";
              }
            }
            return true;
          },
        ],
      },
      row: structuredClone(this.oldRow || EMPTY_ROW),
    };
  },
  computed: {
    ...mapState(useAdminStore, ["normalLibraries"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
    }),
    paths() {
      return this.nameSet(this.normalLibraries, "path", this.oldRow, false);
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
        this.row = structuredClone(to);
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
