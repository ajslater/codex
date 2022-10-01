<template>
  <v-dialog
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
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
        v-if="enableRegistration"
        v-model="registerMode"
        label="Register"
        ripple
      >
        Register
      </v-switch>
      <SubmitFooter
        :verb="registerMode ? 'Register' : 'Login'"
        table=""
        :disabled="!submitButtonEnabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLogin } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import SubmitFooter from "@/components/submit-footer.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "AuthLoginDialog",
  components: {
    SubmitFooter,
  },
  data() {
    return {
      rules: {
        username: [(v) => !!v || "Username is required"],
        password: [(v) => !!v || "Password is required"],
        passwordConfirm: [
          (v) => v === this.credentials.password || "Passwords must match",
        ],
      },
      credentials: {
        username: "",
        password: "",
        passwordConfirm: "",
      },
      submitButtonEnabled: false,
      showDialog: false,
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
    submitButtonLabel: function () {
      return this.registerMode ? "Register" : "Login";
    },
  },
  watch: {
    showDialog() {
      const form = this.$refs.form;
      if (form) {
        this.$refs.form.reset();
      }
    },
    credentials: {
      handler() {
        const form = this.$refs.form;
        this.submitButtonEnabled = form && form.validate();
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["loadAdminFlags", "login", "register"]),
    submit: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        return;
      }
      const mode = this.registerMode ? "register" : "login";
      this[mode](this.credentials)
        .then(() => {
          this.showDialog = this.formErrors && this.formErrors.length > 0;
          return true;
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
</style>
