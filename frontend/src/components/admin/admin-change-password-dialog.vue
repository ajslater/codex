<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    max-width="22em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn icon ripple v-on="on">
        <v-icon> {{ mdiLockPlusOutline }}</v-icon>
      </v-btn>
    </template>
    <div v-if="formSuccess" id="success">
      {{ formSuccess }}
      <CloseButton @click="showDialog = false" />
    </div>
    <v-form v-else id="authDialog" ref="submitForm">
      <input
        id="usernameInput"
        name="username"
        autocomplete="username"
        disabled
        type="hidden"
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
      <SubmitFooter
        verb="Change"
        table="Password"
        :disabled="!submitButtonEnabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mdiLockPlusOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const MIN_PASSWORD_LENGTH = 4;

export default {
  name: "AdminChangePasswordDialog",
  components: { SubmitFooter, CloseButton },
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
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    submitButtonEnabled: function () {
      return (
        this.credentials.password &&
        this.credentials.password.length >= MIN_PASSWORD_LENGTH &&
        this.credentials.password === this.credentials.passwordConfirm
      );
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["changeUserPassword"]),
    submit() {
      console.log("submit");
      const form = this.$refs.submitForm;
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
#success {
  padding: 10px;
  font-size: larger;
  color: green;
  text-align: center;
}
</style>
