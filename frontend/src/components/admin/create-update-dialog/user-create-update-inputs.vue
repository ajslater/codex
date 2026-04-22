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
      :objs="groups"
      title-key="name"
      group-type
    />
    <!--
      The per-user age-rating ceiling. ``null`` (cleared) means "no
      restriction" on the backend; picking a metron restricts the user
      to comics at or below that index.
    -->
    <v-select
      v-model="row.ageRatingMetron"
      :items="ageRatingChoices"
      label="Age Rating"
      item-title="name"
      item-value="pk"
      clearable
      hide-details="auto"
      placeholder="Unrestricted"
    />
  </div>
</template>

<script>
import { mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/create-update-dialog/relation-picker.vue";
import createUpdateInputsMixin from "@/components/admin/create-update-dialog/create-update-inputs-mixin.js";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = Object.freeze([
  "username",
  "isStaff",
  "isActive",
  "groups",
  "ageRatingMetron",
]);
const EMPTY_ROW = Object.freeze({
  username: "",
  password: "",
  passwordConfirm: "",
  isStaff: false,
  isActive: true,
  groups: [],
  ageRatingMetron: null,
});

export default {
  name: "AdminUserCreateUpdateInputs",
  components: {
    AdminRelationPicker,
  },
  mixins: [createUpdateInputsMixin],
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
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      users: (state) => state.users,
      ageRatingMetrons: (state) => state.ageRatingMetrons,
    }),
    usernames() {
      return this.nameSet(this.users, "username", this.oldRow, true);
    },
    ageRatingChoices() {
      /*
       * Dropdown items come straight from the server-seeded canonical
       * table (:class:`codex.models.age_rating.AgeRatingMetron`).
       */
      return this.ageRatingMetrons || [];
    },
  },
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>
