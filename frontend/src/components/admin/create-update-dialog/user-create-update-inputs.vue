<template>
  <div>
    <v-text-field
      v-model="row.username"
      autocomplete="username"
      label="Username"
      :rules="rules.username"
      :error-messages="fieldErrors.username"
      clearable
      autofocus
      @keydown.enter="$refs.email.focus()"
    />
    <v-text-field
      ref="email"
      v-model="row.email"
      :rules="rules.email"
      :error-messages="fieldErrors.email"
      label="Email"
      autocomplete="email"
      type="email"
      clearable
      hint="Used for password reset links if email is configured."
      persistent-hint
      @keydown.enter="$refs.password && $refs.password.focus()"
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
      :placeholder="UNRESTRICTED_LABEL"
    />
    <!--
      Revoking every key logs out every app and device at once, so it
      lives here behind a confirmation, not as a one-click button in the
      Users table.
    -->
    <div v-if="oldRow" class="userKeys">
      <template v-if="oldRow.apiKeyCount">
        <span>API Keys: {{ oldRow.apiKeyCount }}</span>
        <ConfirmDialog
          button-text="Revoke all keys"
          title-text="Revoke all keys"
          :text="revokeText"
          confirm-text="Revoke"
          color="error"
          variant="tonal"
          size="small"
          @confirm="revokeUserKeys(oldRow.pk)"
        />
      </template>
      <span v-else>No API keys.</span>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import LIMITS from "@/choices/limits.json";
import AdminRelationPicker from "@/components/admin/create-update-dialog/relation-picker.vue";
import createUpdateInputsMixin from "@/components/admin/create-update-dialog/create-update-inputs-mixin.js";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { UNRESTRICTED_LABEL, useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const UPDATE_KEYS = Object.freeze([
  "username",
  "email",
  "isStaff",
  "isActive",
  "groups",
  "ageRatingMetron",
]);
const EMPTY_ROW = Object.freeze({
  username: "",
  email: "",
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
    ConfirmDialog,
  },
  mixins: [createUpdateInputsMixin],
  data() {
    return {
      UNRESTRICTED_LABEL,
      rules: {
        username: [
          (v) => !!v || "Username is required",
          // $notIn passes on blank, so the required rule must stay first.
          ["$notIn", () => this.usernames, "Username already used"],
          ["$maxLength", LIMITS.usernameMaxLength],
        ],
        email: [
          (v) => !v || /.+@.+\..+/.test(v) || "Enter a valid email address",
          ["$maxLength", LIMITS.emailMaxLength],
        ],
        password: [
          (v) => !!v || "Password is required",
          (v) =>
            !v ||
            v.length >= LIMITS.passwordMinLength ||
            `Password must be at least ${LIMITS.passwordMinLength} characters`,
        ],
        passwordConfirm: [
          (v) => v === this.row.password || "Passwords must match",
        ],
      },
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      // The server's reason, bound to the field that caused it.
      fieldErrors: (state) => state.form.fieldErrors,
    }),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      users: (state) => state.users,
      ageRatingMetrons: (state) => state.ageRatingMetrons,
    }),
    ...mapState(useAuthStore, {}),
    revokeText() {
      return (
        `Revoke all of ${this.oldRow.username}'s API keys? Every app and` +
        " device using one is logged out until it gets a new key. A" +
        " Universal Token cannot be made again."
      );
    },
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
  methods: {
    // Reports its own errors; the table reload brings the new count.
    ...mapActions(useAdminStore, ["revokeUserKeys"]),
  },
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>

<style scoped lang="scss">
.userKeys {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}
</style>
