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
      :value="row.userSet"
      label="Users"
      :items="vuetifyUsers"
      @change="row.userSet = $event"
    />
    <AdminRelationPicker
      :value="row.librarySet"
      label="Libraries"
      :items="vuetifyLibraries"
      @change="row.librarySet = $event"
    />
  </div>
</template>

<script>
import _ from "lodash";
import { mapGetters, mapState } from "pinia";

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
    ...mapState(useAdminStore, {
      names: function (state) {
        // TODO make groupNames getter
        const names = new Set();
        for (const group of state.groups) {
          if (!this.oldRow || group.name !== this.oldRow.name) {
            names.add(group.name);
          }
        }
        return names;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyLibraries", "vuetifyUsers"]),
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
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>
