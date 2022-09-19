<template>
  <v-dialog
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="22em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn icon ripple v-on="on">
        <v-icon> {{ mdiLockPlusOutline }}</v-icon>
      </v-btn>
    </template>
    <div v-if="formSuccess" id="success">
      {{ formSuccess }} <v-btn block @click="showDialog = false"> X </v-btn>
    </div>
    <v-form v-else id="authDialog" ref="changePasswordForm">
      <input
        id="usernameInput"
        name="username"
        autocomplete="username"
        disabled
        :value="`User ${username}`"
      />
      <v-text-field
        ref="password"
        v-model="credentials.password"
        autocomplete="new-password"
        label="New Password"
        :rules="passwordRules"
        autofocus
        clearable
        type="password"
        @keydown.enter="$refs.passwordConfirm.focus()"
      />
      <v-text-field
        ref="passwordConfirm"
        v-model="credentials.passwordConfirm"
        autocomplete="new-password"
        label="Confirm Password"
        :rules="passwordConfirmRules"
        clearable
        type="password"
      />
      <div>
        <v-btn
          ripple
          :disabled="!changePasswordButtonEnabled"
          @click="changePassword"
        >
          Change Password
        </v-btn>
        <v-btn id="cancelButton" @click="showDialog = false">Cancel</v-btn>
      </div>
      <footer id="messageFooter">
        <small v-if="formErrors && formErrors.length > 0" id="error">
          <div v-for="error in formErrors" :key="error">
            {{ error }}
          </div>
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLockPlusOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

const MIN_PASSWORD_LENGTH = 4;

export default {
  name: "AdminChangePasswordDialog",
  props: {
    pk: {
      type: Number,
      required: true,
    },
    username: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      passwordRules: [
        (v) => {
          if (!v) {
            return "New Password is required";
          }
          if (v.length < MIN_PASSWORD_LENGTH) {
            return `Password must be ${MIN_PASSWORD_LENGTH} characters long.`;
          }
          if (v === this.credentials.oldPassword) {
            return "New password must be different than old password";
          }
          return true;
        },
      ],
      passwordConfirmRules: [
        (v) => v === this.credentials.password || "Passwords must match",
      ],
      credentials: {
        oldPassword: "",
        password: "",
        passwordConfirm: "",
      },
      mdiLockPlusOutline,
      showDialog: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    changePasswordButtonEnabled: function () {
      return (
        this.credentials.password &&
        this.credentials.password.length >= MIN_PASSWORD_LENGTH &&
        this.credentials.password === this.credentials.passwordConfirm
      );
    },
  },
  watch: {
    showDialog(to) {
      if (to) {
        this.clearErrors();
      }
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["changeUserPassword", "clearErrors"]),
    changePassword: function () {
      const form = this.$refs.changePasswordForm;
      if (!form.validate()) {
        return;
      }
      this.changeUserPassword(this.pk, {
        password: this.credentials.password,
      })
        .then(() => {
          // this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
      form.reset();
    },
  },
};
</script>

<style scoped lang="scss">
#authDialog {
  padding: 20px;
}
#usernameInput {
  font-size: x-large;
  font-weight: bold;
  color: white;
}
#messageFooter {
  padding-top: 10px;
}
#error {
  color: red;
}
#success {
  padding: 10px;
  font-size: larger;
  color: green;
  text-align: center;
}
#cancelButton {
  float: right;
}
</style>
