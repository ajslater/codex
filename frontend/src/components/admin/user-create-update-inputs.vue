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
    <v-checkbox v-model="row.isStaff" label="Is Staff" ripple />
    <v-checkbox v-model="row.isActive" label="Is Active" ripple />
    <AdminRelationPicker
      v-model="row.groups"
      label="Groups"
      :items="vuetifyGroups"
    />
  </div>
</template>

<script>
import _ from "lodash";
import { mapGetters, mapState } from "pinia";

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
    ...mapState(useAdminStore, {
      usernames: function (state) {
        // TODO make userUsernames getter
        const names = new Set();
        for (const user of state.users) {
          if (!this.oldRow || user.username !== this.oldRow.username) {
            names.add(user.username);
          }
        }
        return names;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
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
