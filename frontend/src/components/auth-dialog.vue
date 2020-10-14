<template>
  <div v-if="user" id="userMenu">
    <v-list-item v-if="isAdmin" :href="adminURL">
      <v-list-item-content>
        <v-list-item-title>Admin Panel</v-list-item-title>
      </v-list-item-content>
    </v-list-item>
    <v-list-item @click="logout">
      <v-list-item-content>
        <v-list-item-title> Logout {{ user.username }} </v-list-item-title>
      </v-list-item-content>
    </v-list-item>
  </div>
  <v-dialog
    v-else
    v-model="showLoginDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
    @focus="focus()"
  >
    <template #activator="{ on }">
      <v-list-item v-on="on" @click="loginDialogOpened">
        <v-list-item-content>
          <v-list-item-title> Login </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
    <v-form id="authDialog" ref="loginForm">
      <v-text-field
        v-model="credentials.username"
        autocomplete="username"
        :error-messages="usernameErrors"
        label="Username"
        :rules="usernameRules"
        clearable
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <v-text-field
        ref="password"
        v-model="credentials.password"
        :autocomplete="registerMode ? 'new-password' : 'current-password'"
        :error-messages="passwordErrors"
        label="Password"
        :rules="passwordRules"
        clearable
        type="password"
        @keydown.enter="
          if (registerMode) {
            $refs.confirmPassword.focus();
          } else {
            processLogin();
          }
        "
      />
      <v-expand-transition>
        <v-text-field
          v-if="registerMode"
          ref="confirmPassword"
          v-model="confirmPassword"
          label="Confirm Password"
          :rules="confirmPasswordRules"
          clearable
          type="password"
          @keydown.enter="processLogin"
        />
      </v-expand-transition>
      <v-btn ripple @click="processLogin">
        {{ loginButtonLabel }}
      </v-btn>
      <v-switch
        v-if="enableRegistration"
        v-model="registerMode"
        label="Register"
        ripple
      >
        Register
      </v-switch>
      <footer>
        <small v-if="authFormError" style="color: red">
          {{ authFormError }}
        </small>
        <small v-else-if="enableRegistration"
          >Registering preserves bookmarks and settings across different
          browsers</small
        >
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mapState } from "vuex";

import { ADMIN_URL } from "@/api/v2/base";

export default {
  name: "AuthDialog",
  data() {
    return {
      usernameRules: [(v) => !!v || "Username is required"],
      passwordRules: [(v) => !!v || "Password is required"],
      confirmPasswordRules: [
        (v) => v === this.credentials.password || "Passwords must match",
      ],
      credentials: {
        username: "",
        password: "",
      },
      confirmPassword: "",
      showLoginDialog: false,
      registerMode: false,
      adminURL: ADMIN_URL,
    };
  },
  computed: {
    ...mapState("auth", {
      user: (state) => state.user,
      isAdmin: (state) => state.user && state.user.is_staff,
      authFormError: (state) => state.form.error,
      usernameErrors: (state) => state.form.usernameErrors,
      passwordErrors: (state) => state.form.passwordErrors,
      enableRegistration: (state) => state.enableRegistration,
    }),
    loginButtonLabel: function () {
      if (this.registerMode) {
        return "Register";
      } else {
        return "Login";
      }
    },
  },
  methods: {
    closeForm: function () {
      if (this.validationError !== undefined) {
        this.showLoginDialog = false;
        const form = this.$refs.loginForm;
        form.reset();
      }
    },
    processAuth: function (mode) {
      // const oldUser = this.user;
      this.$store.dispatch(`auth/${mode}`, this.credentials).catch((error) => {
        console.error(error);
      });
      return this.closeForm;
    },
    processLogin: function () {
      let mode;
      if (this.registerMode) {
        mode = "register";
      } else {
        mode = "login";
      }
      const form = this.$refs.loginForm;
      if (!form.validate()) {
        return;
      }
      this.processAuth(mode);
    },
    logout: function () {
      this.processAuth("logout");
    },
    loginDialogOpened: function () {
      this.$store.dispatch("auth/loginDialogOpened");
    },
    focus: function () {
      this.$emit("sub-dialog-open");
    },
  },
};
</script>

<style scoped lang="scss">
#userMenu {
  background-color: #121212;
}
#authDialog {
  padding: 20px;
}
</style>
