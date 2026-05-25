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
        v-model="profile.email"
        :rules="rules.email"
        type="email"
        autocomplete="email"
        label="Email"
        clearable
        hint="Only used to receive password reset links."
        persistent-hint
      />
      <v-expansion-panels v-model="passwordPanel" class="passwordSection">
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
      mdiAccountCog,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
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
    canSubmit() {
      const profileChanged = Object.keys(this.diff).length > 0;
      const passwordFilled =
        this.passwordSectionActive &&
        this.profile.oldPassword &&
        this.profile.password &&
        this.profile.passwordConfirm;
      return (profileChanged || passwordFilled) && this.submitButtonEnabled;
    },
  },
  watch: {
    showProfileDialog(open) {
      if (open) {
        this.reset();
      }
    },
  },
  // Used by the auth-form-mixin watcher (it deep-watches `credentials`).
  // We watch `profile` instead by aliasing it under the same name.
  created() {
    this.credentials = this.profile;
  },
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

.passwordSection {
  margin-top: 0.5em;
}

.codexFormSuccess {
  padding: 10px;
  font-size: larger;
  color: rgb(var(--v-theme-success));
  text-align: center;
}
</style>
