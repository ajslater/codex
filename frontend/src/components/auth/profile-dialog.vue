<template>
  <v-dialog
    v-if="user"
    v-model="showProfileDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="24em"
  >
    <template #activator="{ props }">
      <CodexListItem
        v-bind="props"
        :prepend-icon="mdiAccountCog"
        title="Profile"
      />
    </template>
    <div v-if="formSuccess" class="codexFormSuccess">
      {{ formSuccess }}
      <CloseButton @click="showProfileDialog = false" />
    </div>
    <v-form v-else ref="form" class="profileForm">
      <h2>Profile</h2>
      <v-text-field
        v-model="profile.username"
        :rules="rules.username"
        :readonly="usernameLocked"
        :hint="usernameHint"
        :persistent-hint="!usernameLocked"
        autocomplete="username"
        label="Username"
        clearable
      />
      <v-text-field
        v-if="emailEnabled"
        v-model="profile.email"
        :rules="rules.email"
        type="email"
        autocomplete="email"
        label="Email"
        clearable
        hint="Only used to receive password reset links."
        persistent-hint
      />
      <v-expansion-panels v-else v-model="emailPanel" class="collapsedSection">
        <v-expansion-panel value="email">
          <v-expansion-panel-title>Email</v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-text-field
              v-model="profile.email"
              :rules="rules.email"
              type="email"
              autocomplete="email"
              label="Email"
              clearable
              hint="No mail server is configured, so password reset is unavailable. Set this for when one is."
              persistent-hint
            />
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
      <v-expansion-panels v-model="passwordPanel" class="collapsedSection">
        <v-expansion-panel value="password">
          <v-expansion-panel-title>Change Password</v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-text-field
              v-model="profile.oldPassword"
              :rules="passwordRules.oldPassword"
              autocomplete="current-password"
              label="Old Password"
              type="password"
              clearable
            />
            <v-text-field
              v-model="profile.password"
              :rules="passwordRules.password"
              autocomplete="new-password"
              label="New Password"
              type="password"
              clearable
            />
            <v-text-field
              v-model="profile.passwordConfirm"
              :rules="passwordRules.passwordConfirm"
              autocomplete="new-password"
              label="Confirm New Password"
              type="password"
              clearable
            />
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
      <AuthTokenDialog :user="user" />
      <SubmitFooter
        verb="Save"
        table="Profile"
        :disabled="!canSubmit"
        @submit="submit"
        @cancel="showProfileDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiAccountCog } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import authFormMixin from "@/components/auth/auth-form-mixin";
import CloseButton from "@/components/close-button.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import AuthTokenDialog from "@/components/auth/auth-token.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "ProfileDialog",
  components: {
    AuthTokenDialog,
    CloseButton,
    CodexListItem,
    SubmitFooter,
  },
  mixins: [authFormMixin],
  data() {
    return {
      profile: {
        username: "",
        email: "",
        oldPassword: "",
        password: "",
        passwordConfirm: "",
      },
      passwordPanel: null,
      emailPanel: null,
      mdiAccountCog,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
      emailEnabled: (state) => state.adminFlags.emailEnabled,
      remoteUserEnabled: (state) => state.adminFlags.remoteUserEnabled,
      MIN_PASSWORD_LENGTH: (state) => state.MIN_PASSWORD_LENGTH,
    }),
    ...mapWritableState(useAuthStore, ["showProfileDialog"]),
    usernameLocked() {
      return Boolean(this.remoteUserEnabled);
    },
    usernameHint() {
      if (this.usernameLocked) {
        return "Managed by upstream authentication.";
      }
      return "Changing your username will require updating any OPDS or API clients configured with the old name.";
    },
    passwordSectionActive() {
      return this.passwordPanel === "password";
    },
    rules() {
      return {
        username: [(v) => Boolean(v) || "Username is required"],
        email: [
          (v) => !v || /.+@.+\..+/.test(v) || "Enter a valid email address",
        ],
      };
    },
    passwordRules() {
      // Only enforce password validators when the section is open; with it
      // collapsed the user is editing username/email only and the password
      // fields stay empty.
      if (!this.passwordSectionActive) {
        return {
          oldPassword: [],
          password: [],
          passwordConfirm: [],
        };
      }
      return {
        oldPassword: [(v) => Boolean(v) || "Old password is required"],
        password: [
          (v) => {
            if (!v) {
              return "New password is required";
            }
            if (v.length < this.MIN_PASSWORD_LENGTH) {
              return `Password must be at least ${this.MIN_PASSWORD_LENGTH} characters`;
            }
            if (v === this.profile.oldPassword) {
              return "New password must differ from old password";
            }
            return true;
          },
        ],
        passwordConfirm: [
          (v) => v === this.profile.password || "Passwords must match",
        ],
      };
    },
    diff() {
      // Send only fields the user actually edited. Empty strings on
      // optional fields like email clear them - the API treats null and
      // "" as "unset" for the email column.
      const out = {};
      if (
        !this.usernameLocked &&
        this.profile.username &&
        this.profile.username !== this.user.username
      ) {
        out.username = this.profile.username;
      }
      if ((this.profile.email || "") !== (this.user.email || "")) {
        out.email = this.profile.email || "";
      }
      return out;
    },
    isValid() {
      // Synchronous, client-side validity that mirrors the field `:rules`, so
      // the Save button stays in lockstep with the inline errors the user sees
      // while typing — without calling the async form.validate(). The password
      // rules only gate Save once the user actually starts entering a password;
      // an open-but-empty "Change Password" panel shouldn't block a profile
      // edit. submit() still runs the authoritative form.validate().
      const passes = (rules, value) =>
        rules.every((rule) => rule(value) === true);
      if (!passes(this.rules.username, this.profile.username)) {
        return false;
      }
      if (!passes(this.rules.email, this.profile.email)) {
        return false;
      }
      const enteringPassword = Boolean(
        this.profile.oldPassword ||
        this.profile.password ||
        this.profile.passwordConfirm,
      );
      if (enteringPassword) {
        const { oldPassword, password, passwordConfirm } = this.passwordRules;
        if (
          !passes(oldPassword, this.profile.oldPassword) ||
          !passes(password, this.profile.password) ||
          !passes(passwordConfirm, this.profile.passwordConfirm)
        ) {
          return false;
        }
      }
      return true;
    },
    canSubmit() {
      // Enable Save only when there is a change to save AND every field is
      // client-side valid. Each field also validates itself inline as you
      // type (Vuetify's default validate-on="input").
      const profileChanged = Object.keys(this.diff).length > 0;
      const passwordFilled =
        this.passwordSectionActive &&
        this.profile.oldPassword &&
        this.profile.password &&
        this.profile.passwordConfirm;
      return Boolean(profileChanged || passwordFilled) && this.isValid;
    },
  },
  watch: {
    showProfileDialog(open) {
      if (open) {
        this.reset();
      }
    },
  },
  // This dialog opts out of the auth-form-mixin's live `credentials` watcher
  // (we don't alias `profile` onto `credentials`), so the mixin never
  // re-validates the *whole* form on every keystroke — that flashed "required"
  // errors on fields the user hadn't touched yet. Each field still validates
  // itself inline as you type, and `canSubmit`/`isValid` gate the Save button
  // synchronously. (The mixin is still used for keyup blocking + form state.)
  methods: {
    ...mapActions(useAuthStore, [
      "updateProfile",
      "changePassword",
      "loadProfile",
    ]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    reset() {
      this.profile.username = this.user.username || "";
      this.profile.email = this.user.email || "";
      this.profile.oldPassword = "";
      this.profile.password = "";
      this.profile.passwordConfirm = "";
      this.passwordPanel = null;
      this.emailPanel = null;
      this.clearErrors();
    },
    async submit() {
      const form = this.$refs.form;
      if (!form) {
        return;
      }
      const { valid } = await form.validate();
      if (!valid) {
        return;
      }
      const profileDiff = this.diff;
      const wantsPasswordChange =
        this.passwordSectionActive && this.profile.password;
      if (Object.keys(profileDiff).length > 0) {
        const ok = await this.updateProfile(profileDiff);
        if (!ok) {
          return;
        }
      }
      if (wantsPasswordChange) {
        await this.changePassword({
          oldPassword: this.profile.oldPassword,
          password: this.profile.password,
        });
      }
    },
  },
};
</script>

<style scoped lang="scss">
.profileForm {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.collapsedSection {
  margin-top: 0.5em;
}

.codexFormSuccess {
  padding: 10px;
  font-size: larger;
  color: rgb(var(--v-theme-success));
  text-align: center;
}
</style>
