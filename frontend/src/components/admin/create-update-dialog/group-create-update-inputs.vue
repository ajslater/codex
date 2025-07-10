<template>
  <div>
    <v-text-field
      v-model="row.name"
      label="Group Name"
      :rules="rules.name"
      clearable
      autofocus
    />
    <v-radio-group
      inline
      label="Type"
      :model-value="row.exclude"
      hide-details="auto"
      @update:model-value="row.exclude = $event"
    >
      <v-radio :value="false">
        <template #label>
          <GroupChip
            :item="{ name: 'Include', exclude: false }"
            title-key="name"
            group-type
          />
        </template>
      </v-radio>
      <v-radio :value="true">
        <template #label>
          <GroupChip
            :item="{ name: 'Exclude', exclude: true }"
            title-key="name"
            group-type
          />
        </template>
      </v-radio>
    </v-radio-group>
    <AdminRelationPicker
      :model-value="row.userSet"
      label="Users"
      :objs="users"
      title-key="username"
      @update:model-value="row.userSet = $event"
    />
    <AdminRelationPicker
      :model-value="row.librarySet"
      label="Libraries"
      :objs="normalLibraries"
      title-key="path"
      @update:model-value="row.librarySet = $event"
    />
  </div>
</template>

<script>
import deepClone from "deep-clone";
import { mapActions, mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/create-update-dialog/relation-picker.vue";
import GroupChip from "@/components/admin/group-chip.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["name", "userSet", "librarySet", "exclude"];
Object.freeze(UPDATE_KEYS);
const EMPTY_ROW = {
  name: "",
  userSet: [],
  librarySet: [],
  exclude: false,
};
Object.freeze(EMPTY_ROW);

export default {
  name: "AdminGroupCreateUpdateInputs",
  components: {
    AdminRelationPicker,
    GroupChip,
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
        name: [
          (v) => !!v || "Name is required",
          (v) => (!!v && !this.names.has(v.trim())) || "Name already used",
        ],
      },
      row: { ...EMPTY_ROW, ...deepClone(this.oldRow) },
    };
  },
  computed: {
    ...mapState(useAdminStore, ["normalLibraries"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      users: (state) => state.users,
    }),
    names() {
      return this.nameSet(this.groups, "name", this.oldRow, true);
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
        this.row = deepClone(to);
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
