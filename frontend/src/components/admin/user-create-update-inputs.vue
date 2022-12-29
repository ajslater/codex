<template>
  <div>
    <v-text-field
      v-model="row.username"
      autocomplete="username"
      label="Username"
      :rules="rules.username"
      clearable
      autofocus
      @keydown.enter="$refs.password.focus()"
    />
    <div v-if="!oldRow">
      <v-text-field
        ref="password"
        v-model="row.password"
        autocomplete="new-password"
        label="Password"
        :rules="rules.password"
        clearable
        type="password"
        @keydown.enter="$refs.passwordConfirm.focus()"
      />
      <v-text-field
        ref="passwordConfirm"
        v-model="row.passwordConfirm"
        autocomplete="new-password"
        label="Confirm Password"
        :rules="rules.passwordConfirm"
        clearable
        type="password"
      />
    </div>
    <v-checkbox v-model="row.isStaff" label="Is Staff" />
    <v-checkbox v-model="row.isActive" label="Is Active" />
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
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["username", "isStaff", "isActive", "groups"];
Object.freeze(UPDATE_KEYS);
const EMPTY_ROW = {
  username: "",
  password: "",
  passwordConfirm: "",
  isStaff: false,
  isActive: true,
  groups: [],
};
Object.freeze(EMPTY_ROW);

export default {
  name: "AdminUserCreateUpdateInputs",
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
        username: [
          (v) => !!v || "Username is required",
          (v) =>
            (!!v && !this.usernames.has(v.trim())) || "Username already used",
        ],
        password: [(v) => !!v || "Password is required"],
        passwordConfirm: [
          (v) => v === this.row.password || "Passwords must match",
        ],
      },
      row: _.cloneDeep(this.oldRow || EMPTY_ROW),
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    ...mapState(useAdminStore, { users: (state) => state.users }),
    usernames() {
      return this.nameSet(this.users, "username", this.oldRow, true);
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
