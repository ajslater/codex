<template>
  <v-dialog
    v-model="showLoginDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
  >
    <template #activator="{ props }">
      <CodexListItem
        v-bind="props"
        :prepend-icon="mdiLogin"
        :title="loginLabel"
      />
    </template>
    <v-form id="authDialog" ref="form">
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

import CodexListItem from "@/components/codex-list-item.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AuthLoginDialog",
  components: {
    SubmitFooter,
    CodexListItem,
  },
  data() {
    return {
      rules: {
        username: [(v) => !!v || "Username is required"],
        password: [
          (v) => {
            if (!v) {
              return "Password is required";
            }
            if (this.registerMode && v.length < this.MIN_PASSWORD_LEN) {
              return `Password must be ${this.MIN_PASSWORD_LEN} characters long`;
            }
            return true;
          },
        ],
        passwordConfirm: [
          (v) => v === this.credentials.password || "Passwords must match",
        ],
      },
      formModel: {},
      credentials: {
        username: "",
        password: "",
        passwordConfirm: "",
      },
      submitButtonEnabled: false,
      registerMode: false,
      mdiLogin,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    ...mapState(useAuthStore, {
      adminFlags: (state) => state.adminFlags,
      MIN_PASSWORD_LEN: (state) => state.MIN_PASSWORD_LEN,
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
    credentials: {
      handler() {
        const form = this.$refs.form;
        if (form) {
          form
            .validate()
            .then(({ valid }) => {
              this.submitButtonEnabled = valid;
              return this.submitButtonEnabled;
            })
            .catch(console.error);
        } else {
          this.submitButtonEnabled = false;
        }
      },
      deep: true,
    },
  },
  mounted() {
    globalThis.addEventListener("keyup", this._keyUpListener);
  },
  beforeUnmount() {
    globalThis.removeEventListener("keyup", this._keyUpListener);
  },
  methods: {
    ...mapActions(useAuthStore, ["loadAdminFlags", "login", "register"]),
    doAuth(mode) {
      return this[mode](this.credentials)
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
    _keyUpListener(event) {
      // stop keys from activating reader shortcuts.
      event.stopImmediatePropagation();
    },
  },
};
</script>

<style scoped lang="scss">
#authDialog {
  padding: 20px;
}
</style>
