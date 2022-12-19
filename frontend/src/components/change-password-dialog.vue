<template>
  <v-dialog
    v-if="user"
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="22em"
  >
    <template #activator="{ props }">
      <v-btn v-if="isAdminMode" icon v-bind="props">
        <v-icon> {{ mdiLockPlusOutline }}</v-icon>
      </v-btn>
      <v-list-item v-else v-bind="props">
        <v-list-item-title>
          <v-icon>{{ mdiLockReset }}</v-icon
          >Change Password
        </v-list-item-title>
      </v-list-item>
    </template>
    <div v-if="formSuccess" class="codexFormSuccess">
      {{ formSuccess }}
      <CloseButton @click="showDialog = false" />
    </div>
    <v-form v-else ref="form" class="changePasswordForm">
      <h2>User {{ user.username }}</h2>
      <input
        name="username"
        autocomplete="username"
        disabled
        type="text"
        class="hidden"
        :value="user.username"
      />
      <v-text-field
        v-if="!isAdminMode"
        ref="oldPassword"
        v-model="credentials.oldPassword"
        autocomplete="current-password"
        label="Old Password"
        :rules="rules.oldPassword"
        clearable
        type="password"
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <v-text-field
        ref="password"
        v-model="credentials.password"
        autocomplete="new-password"
        label="New Password"
        :rules="rules.password"
        clearable
        type="password"
        :autofocus="isAdminMode"
        @keydown.enter="$refs.passwordConfirm.focus()"
      />
      <v-text-field
        ref="passwordConfirm"
        v-model="credentials.passwordConfirm"
        autocomplete="new-password"
        label="Confirm Password"
        :rules="rules.passwordConfirm"
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
import { mdiLockPlusOutline, mdiLockReset } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "ChangePasswordDialog",
  components: {
    SubmitFooter,
    CloseButton,
  },
  props: {
    user: { type: Object, required: true },
    isAdminMode: { type: Boolean, default: false },
  },
  data() {
    return {
      rules: {
        oldPassword: [(v) => !!v || "Old Password is required"],
        password: [
          (v) => {
            if (!v) {
              return "New Password is required";
            }
            if (v.length < this.MIN_PASSWORD_LENGTH) {
              return `Password must be ${this.MIN_PASSWORD_LENGTH} characters long`;
            }
            if (v === this.credentials.oldPassword) {
              return "New password must be different than old password";
            }
            return true;
          },
        ],
        passwordConfirm: [
          (v) => v === this.credentials.password || "Passwords must match",
        ],
      },
      credentials: {
        oldPassword: "",
        password: "",
        passwordConfirm: "",
      },
      submitButtonEnabled: false,
      showDialog: false,
      mdiLockReset,
      mdiLockPlusOutline,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
      MIN_PASSWORD_LEN: (state) => state.MIN_PASSWORD_LEN,
    }),
  },
  watch: {
    showDialog(to) {
      if (to) {
        const form = this.$refs.form;
        if (form) {
          form.reset();
        }
        this.clearErrors();
      }
    },
    credentials: {
      handler() {
        const form = this.$refs.form;
        if (!form) {
          this.submitButtonEnabled = false;
          return;
        }
        form
          .validate()
          .then(({ valid }) => {
            return (this.submitButtonEnabled = valid);
          })
          .catch(() => {
            this.submitButtonEnabled = false;
          });
      },
      deep: true,
    },
  },
  mounted() {
    window.addEventListener("keyup", this._keyListener);
  },
  unmounted() {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions(useAuthStore, ["changePassword"]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    doUserChange() {
      return useAdminStore()
        .changeUserPassword(this.user.pk, this.credentials)
        .catch(console.error);
    },
    doSelfChange() {
      return this.changePassword(this.credentials).catch(console.error);
    },
    submit() {
      const form = this.$refs.form;
      if (!form) {
        return;
      }
      form
        .validate()
        .then(({ valid }) => {
          if (!valid) {
            return;
          } else if (this.isAdminMode) {
            return this.doUserChange();
          } else {
            return this.doSelfChange();
          }
        })
        .catch(console.error);
    },
    _keyListener(event) {
      // stop keys from activating reader shortcuts.
      event.stopImmediatePropagation();
    },
  },
};
</script>

<style scoped lang="scss">
.changePasswordForm {
  padding: 20px;
}
.codexFormSuccess {
  padding: 10px;
  font-size: larger;
  color: rgb(var(--v-theme-success));
  text-align: center;
}
.hidden {
  display: none;
}
</style>
