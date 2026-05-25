<template>
  <v-container class="resetConfirmContainer">
    <v-card class="resetConfirmCard" max-width="22em">
      <v-card-title>Reset Password</v-card-title>
      <v-card-text>
        <div v-if="!signaturePresent" class="codexFormError">
          This password-reset link is missing required parameters. Use the link
          from the most recent reset email, or request a new one.
        </div>
        <div v-else-if="formSuccess" class="codexFormSuccess">
          {{ formSuccess }}
        </div>
        <v-form v-else ref="form">
          <p class="hint">Choose a new password for your Codex account.</p>
          <v-text-field
            v-model="password"
            :rules="rules.password"
            autocomplete="new-password"
            label="New Password"
            type="password"
            autofocus
            clearable
            @keydown.enter="$refs.passwordConfirm.focus()"
          />
          <v-text-field
            ref="passwordConfirm"
            v-model="passwordConfirm"
            :rules="rules.passwordConfirm"
            autocomplete="new-password"
            label="Confirm Password"
            type="password"
            clearable
            @keydown.enter="submit"
          />
          <SubmitFooter
            verb="Reset"
            table="Password"
            :disabled="!canSubmit"
            @submit="submit"
            @cancel="goHome"
          />
        </v-form>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script>
import { mapActions, mapState } from "pinia";

import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "ResetPasswordConfirm",
  components: {
    SubmitFooter,
  },
  data() {
    return {
      password: "",
      passwordConfirm: "",
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      MIN_PASSWORD_LENGTH: (state) => state.MIN_PASSWORD_LENGTH,
    }),
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    signaturePresent() {
      // rest-registration emits snake_case query params in the email
      // link. Read them as-is from the URL even though the JSON API
      // request below uses camelCase keys (the parser snake_case-ifies).
      const q = this.$route.query;
      return Boolean(q.user_id && q.timestamp && q.signature);
    },
    rules() {
      return {
        password: [
          (v) => {
            if (!v) {
              return "Password is required";
            }
            if (v.length < this.MIN_PASSWORD_LENGTH) {
              return `Password must be at least ${this.MIN_PASSWORD_LENGTH} characters`;
            }
            return true;
          },
        ],
        passwordConfirm: [(v) => v === this.password || "Passwords must match"],
      };
    },
    canSubmit() {
      return Boolean(this.password) && this.password === this.passwordConfirm;
    },
  },
  beforeMount() {
    // Surface a fresh form state on direct navigation to this route.
    useCommonStore().clearErrors();
  },
  methods: {
    ...mapActions(useAuthStore, ["resetPassword"]),
    goHome() {
      this.$router.push({ name: "home" });
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
      const { user_id, timestamp, signature } = this.$route.query;
      // The Codex JSON parser snake_case-ifies camelCase keys before the
      // serializer sees them, so we send camelCase here.
      const ok = await this.resetPassword({
        userId: user_id,
        timestamp: Number(timestamp),
        signature,
        password: this.password,
      });
      if (ok) {
        // Allow the success banner to remain visible briefly, then route home.
        setTimeout(() => this.goHome(), 2000);
      }
    },
  },
};
</script>

<style scoped lang="scss">
.resetConfirmContainer {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 4em;
}

.resetConfirmCard {
  padding: 1em;
}

.hint {
  font-size: 0.875em;
  color: rgba(var(--v-theme-on-surface), 0.75);
  margin-bottom: 1em;
}

.codexFormError {
  color: rgb(var(--v-theme-error));
  text-align: center;
}

.codexFormSuccess {
  color: rgb(var(--v-theme-success));
  text-align: center;
  font-size: larger;
}
</style>
