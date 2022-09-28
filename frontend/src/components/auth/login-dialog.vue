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
      <v-list-item ripple v-on="on" @click="loadAdminFlags">
        <v-list-item-content>
          <v-list-item-title
            ><h3>
              <v-icon>{{ mdiLogin }}</v-icon
              >Login
            </h3></v-list-item-title
          >
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
        <small v-if="formErrors && formErrors.length > 0" style="color: red">
          <div v-for="error in formErrors" :key="error">
            {{ error }}
          </div>
        </small>
        <small v-else-if="formSuccess" style="color: green"
          >{{ formSuccess }}
        </small>
        <small v-else-if="enableRegistration">
          Registering preserves bookmarks and settings across different browsers
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

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
      mdiLogin,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
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
    ...mapActions(useAuthStore, [
      "clearErrors",
      "loadAdminFlags",
      "login",
      "register",
    ]),
    processAuth: function (mode) {
      this[mode](this.credentials).catch((error) => {
        console.error(error);
      });
      if (!this.formErrors || this.formErrors === []) {
        this.showLoginDialog = false;
        this.$refs.loginForm.reset();
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
