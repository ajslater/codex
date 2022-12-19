<template>
  <div>
    <v-text-field
      v-model="row.name"
      label="Group Name"
      :rules="rules.name"
      clearable
      autofocus
    />
    <AdminRelationPicker
      :model-value="row.userSet"
      label="Users"
      :items="vuetifyUsers"
      @update:model-value="row.userSet = $event"
    />
    <AdminRelationPicker
      :model-value="row.librarySet"
      label="Libraries"
      :items="vuetifyLibraries"
      @update:model-value="row.librarySet = $event"
    />
  </div>
</template>

<script>
import _ from "lodash";
import { mapActions, mapGetters, mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["name", "userSet", "librarySet"];
Object.freeze(UPDATE_KEYS);
const EMPTY_ROW = {
  name: "",
  userSet: [],
  librarySet: [],
};
Object.freeze(EMPTY_ROW);

export default {
  name: "AdminGroupCreateUpdateInputs",
  components: {
    AdminRelationPicker,
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
      row: _.cloneDeep(this.oldRow || EMPTY_ROW),
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["vuetifyLibraries", "vuetifyUsers"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
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
