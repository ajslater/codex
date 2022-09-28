<template>
  <v-dialog
    v-if="user"
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
    @focus="focus"
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
    </div>
    <v-form v-else id="authDialog" ref="changePasswordForm">
      <h2>User {{ user.username }}</h2>
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
      <v-btn
        ripple
        :disabled="!changePasswordButtonEnabled"
        @click="processChangePassword"
      >
        Change Password
      </v-btn>
      <CancelButton @click="showDialog = false" />
      <footer id="messageFooter">
        <small v-if="formErrors && formErrors.length > 0" id="error">
          <div v-for="error in formErrors" :key="error">
            {{ error }}
          </div>
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLockReset } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CancelButton from "@/components/cancel-button.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AuthChangePasswordDialog",
  components: {
    CancelButton,
  },
  emits: ["sub-dialog-open", "change-password-closed"],
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
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    changePasswordButtonEnabled: function () {
      return (
        this.credentials.oldPassword &&
        this.credentials.oldPassword.length > 0 &&
        this.credentials.password &&
        this.credentials.password.length > 0 &&
        this.credentials.oldPassword !== this.credentials.password &&
        this.credentials.password === this.credentials.passwordConfirm
      );
    },
  },
  watch: {
    showDialog(show) {
      if (show) {
        this.clearErrors();
      } else {
        this.$emit("change-password-closed");
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["changePassword", "clearErrors"]),
    processChangePassword: function () {
      const form = this.$refs.changePasswordForm;
      if (!form.validate()) {
        return;
      }
      this.changePassword(this.credentials).catch((error) => {
        console.error(error);
      });
      form.reset();
    },
    focus: function () {
      this.$emit("sub-dialog-open");
    },
  },
};
</script>

<style scoped lang="scss">
#authDialog {
  padding: 20px;
}
#messageFooter {
  padding-top: 10px;
}
#error {
  color: red;
}
#success {
  padding: 10px;
  font-size: larger;
  color: green;
}
</style>
