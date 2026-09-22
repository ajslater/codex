<template>
  <v-dialog
    v-model="showLoginDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="320"
  >
    <template #activator="{ props }">
      <CodexListItem
        v-bind="props"
        :prepend-icon="mdiLogin"
        :title="loginLabel"
      />
    </template>
    <v-form id="authDialog" ref="form" validate-on="submit">
      <template v-if="adminFlags.oidcEnabled">
        <SsoLoginButton />
        <div class="ssoDivider">or</div>
      </template>
      <v-text-field
        v-model="credentials.username"
        autocomplete="username"
        label="Username"
        :rules="rules.username"
        clearable
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <v-text-field
        ref="password"
        v-model="credentials.password"
        :autocomplete="registerMode ? 'new-password' : 'current-password'"
        label="Password"
        :rules="rules.password"
        clearable
        type="password"
        @keydown.enter="
          if (registerMode) {
            $refs.passwordConfirm.focus();
          } else {
            submit();
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
          :rules="rules.passwordConfirm"
          clearable
          type="password"
          @keydown.enter="
            if (emailRequired) {
              $refs.email.focus();
            } else {
              submit();
            }
          "
        />
      </v-expand-transition>
      <!--
        Email is only collected when ``Verify New User Email`` is on.
        The backend requires an address to send the verification link
        to; the field is hidden otherwise to keep the no-verification
        register flow as short as possible.
      -->
      <v-expand-transition>
        <v-text-field
          v-if="emailRequired"
          ref="email"
          v-model="credentials.email"
          autocomplete="email"
          label="Email"
          type="email"
          :rules="rules.email"
          clearable
          @keydown.enter="submit"
        />
      </v-expand-transition>
      <v-switch
        v-if="adminFlags.registration"
        v-model="registerMode"
        label="Register"
      >
        Register
      </v-switch>
      <ResetPasswordRequestDialog v-if="adminFlags.emailEnabled" />
      <SubmitFooter
        :verb="registerMode ? 'Register' : 'Login'"
        table=""
        :disabled="!submitButtonEnabled"
        @submit="submit"
        @cancel="showLoginDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import LIMITS from "@/choices/limits.json";
import authFormMixin from "@/components/auth/auth-form-mixin";
import ResetPasswordRequestDialog from "@/components/auth/reset-password-request-dialog.vue";
import SsoLoginButton from "@/components/auth/sso-login-button.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthLoginDialog",
  components: {
    SubmitFooter,
    CodexListItem,
    ResetPasswordRequestDialog,
    SsoLoginButton,
  },
  mixins: [authFormMixin],
  data() {
    return {
      rules: {
        username: [(v) => !!v || "Username is required"],
        password: [
          (v) => {
            if (!v) {
              return "Password is required";
            }
            if (this.registerMode && v.length < LIMITS.passwordMinLength) {
              return `Password must be at least ${LIMITS.passwordMinLength} characters`;
            }
            return true;
          },
        ],
        passwordConfirm: [
          (v) => v === this.credentials.password || "Passwords must match",
        ],
        email: [
          (v) => {
            // Validation only fires when the field is rendered, i.e.
            // registerMode + RV admin flag both true — see emailRequired.
            if (!this.emailRequired) {
              return true;
            }
            if (!v) {
              return "Email is required for verification";
            }
            // Minimal shape check — the backend does authoritative
            // validation. Matches the EmailField default behavior of
            // requiring an ``@`` with non-empty local + domain parts.
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || "Email is invalid";
          },
        ],
      },
      formModel: {},
      credentials: {
        username: "",
        password: "",
        passwordConfirm: "",
        email: "",
      },
      registerMode: false,
      mdiLogin,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      adminFlags: (state) => state.adminFlags,
    }),
    ...mapWritableState(useAuthStore, ["showLoginDialog"]),
    submitButtonLabel() {
      return this.registerMode ? "Register" : "Login";
    },
    loginLabel() {
      let label = "Login";
      if (this.adminFlags.registration) {
        label += " or Register";
      }
      return label;
    },
    emailRequired() {
      // The ``Verify New User Email`` admin flag (RV) drives whether
      // the backend sends a verification link, which in turn requires
      // an address to send to. Without RV the address is unused, so
      // the field stays hidden.
      return Boolean(this.registerMode && this.adminFlags.registerVerification);
    },
  },
  watch: {
    showLoginDialog(to) {
      if (to) {
        this.loadAdminFlags();
        const form = this.$refs.form;
        if (form) {
          this.$refs.form.reset();
        }
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["loadAdminFlags", "login", "register"]),
    doAuth(mode) {
      return Reflect.get(this, mode)
        .call(this, this.credentials)
        .then(() => {
          this.showLoginDialog = this.formErrors && this.formErrors.length > 0;
          return this.showLoginDialog;
        })
        .catch(console.error);
    },
    submit() {
      const form = this.$refs.form;
      form
        .validate()
        .then(({ valid }) => {
          if (!valid) {
            return;
          }
          const mode = this.registerMode ? "register" : "login";
          return this.doAuth(mode);
        })
        .catch(console.error);
    },
  },
};
</script>

<style scoped lang="scss">
#authDialog {
  padding: 20px;
}

.ssoDivider {
  text-align: center;
  margin: 0.75em 0;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.875em;
}
</style>
