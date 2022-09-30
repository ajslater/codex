<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <AdminCreateUpdateButton :update="update" table="User" v-on="on" />
    </template>
    <v-form ref="form" class="cuForm">
      <v-text-field
        v-model="user.username"
        autocomplete="username"
        label="Username"
        :rules="usernameRules"
        clearable
        autofocus
        @keydown.enter="$refs.password.focus()"
      />
      <div v-if="!update">
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
        />
      </div>
      <v-checkbox v-model="user.isStaff" label="Is Staff" ripple />
      <v-checkbox v-model="user.isActive" label="Is Active" ripple />
      <AdminRelationPicker
        v-model="user.groups"
        label="Groups"
        :items="vuetifyGroups"
      />
      <SubmitFooter
        :verb="verb"
        table="User"
        :disabled="submitButtonDisabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import AdminCreateUpdateButton from "@/components/admin/create-update-button.vue";
import AdminRelationPicker from "@/components/admin/relation-picker.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["username", "isStaff", "isActive", "groups"];
const EMPTY_USER = {
  username: "",
  password: "",
  passwordConfirm: "",
  isStaff: false,
  isActive: true,
  group: [],
};
Object.freeze(EMPTY_USER);

export default {
  name: "AdminUserCreateUpdateDialog",
  components: {
    AdminCreateUpdateButton,
    SubmitFooter,
    AdminRelationPicker,
  },
  props: {
    update: {
      type: Boolean,
      default: false,
    },
    oldUser: {
      type: Object,
      default: () => {
        return { ...EMPTY_USER };
      },
    },
  },
  data() {
    return {
      usernameRules: [
        (v) => !!v || "Username is required",
        (v) =>
          (!!v && !this.usernames.has(v.trim())) || "Username is already used",
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
      usernames: function (state) {
        const names = new Set();
        for (const user of state.users) {
          if (!this.update || user.username !== this.oldUser.username) {
            names.add(user.username);
          }
        }
        return names;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyGroups"]),
    submitButtonDisabled: function () {
      let changed = false;
      for (const [key, value] of Object.entries(this.user)) {
        if (this.oldUser[key] !== value) {
          changed = true;
          break;
        }
      }
      if (!changed) {
        return true;
      }
      const form = this.$refs.form;
      return !form || !form.validate();
    },
    verb() {
      return this.update ? "Update" : "Add";
    },
  },
  watch: {
    showDialog(show) {
      this.user =
        show && this.update ? this.createUpdateUser() : { ...EMPTY_USER };
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["createRow", "updateRow"]),
    createUpdateUser() {
      const updateUser = {};
      for (const key of UPDATE_KEYS) {
        updateUser[key] = this.oldUser[key];
      }
      return updateUser;
    },
    doUpdate: function () {
      // only pass diff from old user as update
      const updateUser = {};
      for (const [key, value] of Object.entries(this.user)) {
        if (this.oldUser[key] !== value) {
          updateUser[key] = value;
        }
      }
      this.updateRow("User", this.oldUser.pk, updateUser)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    doCreate: function () {
      this.createRow("User", this.user)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    submit: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        console.warn("submit attempted with invalid form");
        return;
      }
      if (this.update) {
        this.doUpdate();
      } else {
        this.doCreate();
      }
    },
  },
};
</script>

<style scoped lang="scss">
.cuForm {
  padding: 20px;
}
</style>
