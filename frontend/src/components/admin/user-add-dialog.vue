<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn ripple rounded v-on="on"> + Add User </v-btn>
    </template>
    <v-form id="userAddDialog" ref="form">
      <v-text-field
        v-model="user.username"
        autocomplete="username"
        label="Username"
        :rules="usernameRules"
        clearable
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <v-text-field
        ref="password"
        v-model="user.password"
        autocomplete="new-password"
        label="Password"
        :rules="passwordRules"
        clearable
        type="password"
        @keydown.enter="$refs.passwordConfirm.focus()"
      />
      <v-text-field
        ref="passwordConfirm"
        v-model="user.passwordConfirm"
        autocomplete="new-password"
        label="Confirm Password"
        :rules="passwordConfirmRules"
        clearable
        type="password"
        @keydown.enter="$refs.addUser.focus()"
      />
      <v-checkbox v-model="user.isStaff" label="Is Staff" ripple />
      <v-checkbox v-model="user.isActive" label="Is Active" ripple />
      <AdminRelationPicker
        :value="user.groupSet"
        label="Groups"
        :items="vuetifyGroups"
        @change="user.groupSet = $event"
      />
      <v-btn
        ref="addUser"
        ripple
        :disabled="!addUserButtonEnabled"
        @click="addUser"
      >
        Add User
      </v-btn>
      <v-btn class="addCancelButton" ripple @click="showDialog = false">
        Cancel
      </v-btn>
      <footer>
        <small v-if="formErrors && formErrors.length > 0" style="color: red">
          <div v-for="error in formErrors" :key="error">
            {{ error }}
          </div>
        </small>
        <small v-else-if="formSuccess" style="color: green"
          >{{ formSuccess }}
        </small>
      </footer>
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import { useAdminStore } from "@/stores/admin";

const EMPTY_USER = {
  username: "",
  password: "",
  passwordConfirm: "",
  isStaff: false,
  isActive: true,
  groupSet: [],
};
Object.freeze(EMPTY_USER);

export default {
  name: "AdminUserAddDialog",
  components: {
    AdminRelationPicker,
  },
  data() {
    return {
      usernameRules: [
        (v) => !!v || "Username is required",
        (v) =>
          (!!v && !this.usernames.includes(v.trim())) ||
          "Username is already used",
      ],
      passwordRules: [(v) => !!v || "Password is required"],
      passwordConfirmRules: [
        (v) => v === this.user.password || "Passwords must match",
      ],
      user: { ...EMPTY_USER },
      showDialog: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      formErrors: (state) => state.errors,
      formSuccess: (state) => state.success,
      usernames: (state) => {
        const names = [];
        for (const user of state.users) {
          names.push(user.username);
        }
        return names;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    addUserButtonEnabled: function () {
      for (const rule of this.usernameRules) {
        if (rule(this.user.username) !== true) {
          return false;
        }
      }
      for (const rule of this.passwordRules) {
        if (rule(this.user.password) !== true) {
          return false;
        }
      }
      for (const rule of this.passwordConfirmRules) {
        if (rule(this.user.passwordConfirm) !== true) {
          return false;
        }
      }
      return true;
    },
  },
  watch: {
    showDialog(show) {
      if (show) {
        this.clearErrors();
      }
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["clearErrors", "createRow"]),
    addUser: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        return;
      }
      this.createRow("User", this.user)
        .then(() => {
          this.showDialog = false;
          this.user = { ...EMPTY_USER };
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
  },
};
</script>

<style scoped lang="scss">
#userAddDialog {
  padding: 20px;
}
</style>
