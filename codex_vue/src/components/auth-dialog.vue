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
  >
    <template #activator="{ on }">
      <v-list-item v-on="on" @click="loginDialogOpened">
        <v-list-item-content>
          <v-list-item-title>
            Login
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
    <v-form ref="loginForm">
      <v-text-field
        v-model="credentials.username"
        :error-messages="usernameErrors"
        label="Username"
        :rules="usernameRules"
        clearable
      />
      <v-text-field
        v-model="credentials.password"
        :error-messages="passwordErrors"
        label="Password"
        :rules="passwordRules"
        clearable
        type="password"
      />
      <v-expand-transition>
        <v-text-field
          v-if="registerMode"
          v-model="confirmPassword"
          label="Confirm Password"
          :rules="confirmPasswordRules"
          clearable
          type="password"
        />
      </v-expand-transition>
      <v-btn v-if="!registerMode" ripple @click="login">
        Login
      </v-btn>
      <v-btn v-else ripple @click="register">
        Register
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
        <small v-if="authFormError" style="color: red;">
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
//import { mdiAccount, mdiAccountOutline } from "@mdi/js";
import { mapState } from "vuex";

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
      adminURL: (state) => state.adminURL,
    }),
    /*
    userIcon() {
      if (this.user) {
        return mdiAccount;
      } else {
        return mdiAccountOutline;
      }
    },
*/
  },
  methods: {
    closeForm: function () {
      const form = this.$refs.loginForm;
      if (this.validationError !== undefined) {
        this.showLoginDialog = false;
        form.reset();
      }
      return true;
    },
    login: function () {
      const form = this.$refs.loginForm;
      if (!form.validate()) {
        return;
      }
      const old_user = this.user;
      this.$store
        .dispatch("auth/login", this.credentials)
        .then(() => {
          if (old_user != this.user) {
            this.$store.dispatch("browser/getBrowseObjects");
          }
          return this.closeForm;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    register: function () {
      const form = this.$refs.loginForm;
      if (!form.validate()) {
        return;
      }
      this.$store
        .dispatch("auth/register", this.credentials)
        .then(this.closeForm)
        .catch((error) => {
          console.error(error);
        });
    },
    logout: function () {
      this.$store
        .dispatch("auth/logout")
        .then(() => {
          return this.$store.dispatch("browser/getBrowseObjects");
        })
        .catch((error) => {
          console.error(error);
        });
    },
    loginDialogOpened: function () {
      this.$store.dispatch("auth/loginDialogOpened");
    },
  },
};
</script>

<style scoped lang="scss">
#userMenu {
  background-color: #121212; /* TODO map theme background */
}
</style>
