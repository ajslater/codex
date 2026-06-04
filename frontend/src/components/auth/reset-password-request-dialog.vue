<template>
  <v-dialog
    v-model="showResetPasswordRequestDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="352"
  >
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        variant="text"
        size="small"
        class="forgotPasswordLink"
      >
        Forgot password?
      </v-btn>
    </template>
    <v-form ref="form" class="resetRequestForm">
      <h2>Reset Password</h2>
      <p class="hint">
        Enter your username or email address. If an account exists, a reset link
        will be sent.
      </p>
      <v-text-field
        v-model="login"
        :rules="rules.login"
        label="Username or Email"
        autofocus
        clearable
        @keydown.enter="submit"
      />
      <SubmitFooter
        verb="Send"
        table="Reset Link"
        :disabled="!login"
        @submit="submit"
        @cancel="close"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapWritableState } from "pinia";

import authFormMixin from "@/components/auth/auth-form-mixin";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "ResetPasswordRequestDialog",
  components: {
    SubmitFooter,
  },
  mixins: [authFormMixin],
  data() {
    return {
      login: "",
      rules: {
        login: [(v) => Boolean(v) || "Username or email is required"],
      },
      // auth-form-mixin deep-watches `credentials` for live validation.
      credentials: { login: "" },
    };
  },
  computed: {
    ...mapWritableState(useAuthStore, ["showResetPasswordRequestDialog"]),
  },
  watch: {
    login(value) {
      this.credentials.login = value;
    },
    showResetPasswordRequestDialog(open) {
      if (open) {
        this.login = "";
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["sendResetPasswordLink"]),
    close() {
      this.showResetPasswordRequestDialog = false;
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
      // The API returns success whether or not the account exists (it
      // deliberately doesn't leak account presence). Close the dialog; the
      // green "Reset link sent" banner on the login screen is the only
      // confirmation needed.
      const ok = await this.sendResetPasswordLink(this.login);
      if (ok) {
        this.close();
      }
    },
  },
};
</script>

<style scoped lang="scss">
.resetRequestForm {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.hint {
  font-size: 0.875em;
  color: rgba(var(--v-theme-on-surface), 0.75);
}

.forgotPasswordLink {
  text-transform: none;
  padding: 0;
  align-self: flex-start;
  font-size: 0.875em;
}
</style>
