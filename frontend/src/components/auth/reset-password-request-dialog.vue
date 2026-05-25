<template>
  <v-dialog
    v-model="showResetPasswordRequestDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="22em"
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
    <div v-if="resetPasswordRequestSent" class="codexFormSuccess">
      If that account has an email on file, a reset link has been sent.
      <CloseButton @click="close" />
    </div>
    <v-form v-else ref="form" class="resetRequestForm">
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
import { mapActions, mapState, mapWritableState } from "pinia";

import authFormMixin from "@/components/auth/auth-form-mixin";
import CloseButton from "@/components/close-button.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "ResetPasswordRequestDialog",
  components: {
    CloseButton,
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
    ...mapState(useAuthStore, {
      resetPasswordRequestSent: (state) => state.resetPasswordRequestSent,
    }),
    ...mapWritableState(useAuthStore, ["showResetPasswordRequestDialog"]),
  },
  watch: {
    login(value) {
      this.credentials.login = value;
    },
    showResetPasswordRequestDialog(open) {
      if (open) {
        this.login = "";
        this.resetSentState(false);
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["sendResetPasswordLink"]),
    resetSentState(value) {
      // Direct store mutation to clear the success state between opens.
      useAuthStore().$patch({ resetPasswordRequestSent: value });
    },
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
      // Returns success regardless of whether the user exists (the API
      // deliberately doesn't leak account presence). Show the same
      // "check your email" message either way.
      await this.sendResetPasswordLink(this.login);
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

.codexFormSuccess {
  padding: 20px;
  font-size: larger;
  color: rgb(var(--v-theme-success));
  text-align: center;
}

.forgotPasswordLink {
  text-transform: none;
  padding: 0;
  align-self: flex-start;
  font-size: 0.875em;
}
</style>
