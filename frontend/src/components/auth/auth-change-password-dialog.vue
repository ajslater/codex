<template>
  <v-dialog
    v-if="user"
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="22em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-list-item ripple v-on="on">
        <v-list-item-content>
          <v-list-item-title
            ><v-icon>{{ mdiLockReset }}</v-icon
            >Change Password</v-list-item-title
          >
        </v-list-item-content>
      </v-list-item>
    </template>
    <div v-if="formSuccess" id="success">
      {{ formSuccess }}
      <CloseButton @click="showDialog = false" />
    </div>
    <v-form v-else id="authDialog" ref="changePasswordForm">
      <h2>User {{ user.username }}</h2>
      <input
        id="usernameInput"
        name="username"
        autocomplete="username"
        disabled
        type="hidden"
        :value="user.username"
      />
      <v-text-field
        ref="oldPassword"
        v-model="credentials.oldPassword"
        autocomplete="current-password"
        label="Old Password"
        :rules="oldPasswordRules"
        clearable
        type="password"
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <v-text-field
        ref="password"
        v-model="credentials.password"
        autocomplete="new-password"
        label="New Password"
        :rules="passwordRules"
        clearable
        type="password"
        @keydown.enter="$refs.passwordConfirm.focus()"
      />
      <v-expand-transition>
        <v-text-field
          ref="passwordConfirm"
          v-model="credentials.passwordConfirm"
          autocomplete="new-password"
          label="Confirm Password"
          :rules="passwordConfirmRules"
          clearable
          type="password"
        />
      </v-expand-transition>
      <SubmitFooter
        verb="Change"
        table="Password"
        :disabled="!changePasswordButtonEnabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLockReset } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
const MIN_PASSWORD_LENGTH = 4;

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AuthChangePasswordDialog",
  components: {
    SubmitFooter,
    CloseButton,
  },
  data() {
    return {
      oldPasswordRules: [(v) => !!v || "Old Password is required"],
      passwordRules: [
        (v) => {
          if (!v) {
            return "New Password is required";
          }
          if (v === this.credentials.oldPassword) {
            return "New password must be different than old password";
          }
          return true;
        },
      ],
      passwordConfirmRules: [
        (v) => v === this.credentials.password || "Passwords must match",
      ],
      credentials: {
        oldPassword: "",
        password: "",
        passwordConfirm: "",
      },
      showDialog: false,
      mdiLockReset,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    changePasswordButtonEnabled: function () {
      return (
        this.credentials.oldPassword &&
        this.credentials.oldPassword.length > 0 &&
        this.credentials.password &&
        this.credentials.password.length > MIN_PASSWORD_LENGTH &&
        this.credentials.oldPassword !== this.credentials.password &&
        this.credentials.password === this.credentials.passwordConfirm
      );
    },
  },
  watch: {
    showDialog() {
      const form = this.$refs.changePasswordForm;
      if (form) {
        form.reset();
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["changePassword"]),
    submit: function () {
      const form = this.$refs.changePasswordForm;
      if (!form.validate()) {
        return;
      }
      this.changePassword(this.credentials).catch((error) => {
        console.error(error);
      });
      form.reset();
    },
  },
};
</script>

<style scoped lang="scss">
#authDialog {
  padding: 20px;
}
#success {
  padding: 10px;
  font-size: larger;
  color: green;
}
</style>
