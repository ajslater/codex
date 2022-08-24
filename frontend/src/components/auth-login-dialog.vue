<template>
  <v-dialog
    v-model="showLoginDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
    @focus="focus"
  >
    <template #activator="{ on }">
      <v-list-item ripple v-on="on" @click="getAdminFlags">
        <v-list-item-content>
          <v-list-item-title><h3>Login</h3></v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
    <v-form id="authDialog" ref="loginForm">
      <v-text-field
        v-model="credentials.username"
        autocomplete="username"
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
        label="Password"
        :rules="passwordRules"
        clearable
        type="password"
        @keydown.enter="
          if (registerMode) {
            $refs.passwordConfirm.focus();
          } else {
            processLogin();
          }
        "
      />
      <v-expand-transition>
        <v-text-field
          v-if="registerMode"
          ref="passwordConfirm"
          v-model="credentials.passwordConfirm"
          autocomplete="new-password"
          label="Confirm Password"
          :rules="passwordConfirmRules"
          clearable
          type="password"
          @keydown.enter="processLogin"
        />
      </v-expand-transition>
      <v-btn ripple :disabled="!loginButtonEnabled" @click="processLogin">
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
        <small
          v-if="authFormErrors && authFormErrors.length > 0"
          style="color: red"
        >
          <div v-for="error in authFormErrors" :key="error">
            {{ error }}
          </div>
        </small>
        <small v-else-if="authFormSuccess" style="color: green"
          >{{ authFormSuccess }}
        </small>
        <small v-else-if="enableRegistration">
          Registering preserves bookmarks and settings across different browsers
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapState } from "vuex";

export default {
  name: "AuthLoginDialog",
  emits: ["sub-dialog-open"],
  data() {
    return {
      usernameRules: [(v) => !!v || "Username is required"],
      passwordRules: [(v) => !!v || "Password is required"],
      passwordConfirmRules: [
        (v) => v === this.credentials.password || "Passwords must match",
      ],
      credentials: {
        username: "",
        password: "",
        passwordConfirm: "",
      },
      showLoginDialog: false,
      registerMode: false,
    };
  },
  computed: {
    ...mapState("auth", {
      authFormErrors: (state) => state.errors,
      authFormSuccess: (state) => state.success,
      enableRegistration: (state) => state.adminFlags.enableRegistration,
    }),
    loginButtonLabel: function () {
      return this.registerMode ? "Register" : "Login";
    },
    loginButtonEnabled: function () {
      return (
        this.credentials.username.length > 0 &&
        this.credentials.password.length > 0 &&
        (!this.registerMode ||
          this.credentials.password == this.credentials.passwordConfirm)
      );
    },
  },
  watch: {
    showLoginDialog(show) {
      if (show) {
        this.clearErrors();
      }
    },
  },
  methods: {
    ...mapActions("auth", [
      "clearErrors",
      "getAdminFlags",
      "login",
      "register",
    ]),
    processAuth: function (mode) {
      this[mode](this.credentials).catch((error) => {
        console.error(error);
      });
      if (this.validationError !== undefined) {
        this.showLoginDialog = false;
        const form = this.$refs.loginForm;
        form.reset();
      }
    },
    processLogin: function () {
      const mode = this.registerMode ? "register" : "login";
      const form = this.$refs.loginForm;
      if (!form.validate()) {
        return;
      }
      this.processAuth(mode);
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
</style>
