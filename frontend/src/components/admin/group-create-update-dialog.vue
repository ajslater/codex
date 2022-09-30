<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <AdminCreateUpdateButton :update="update" table="Group" v-on="on" />
    </template>
    <v-form ref="form" class="cuForm">
      <v-text-field
        v-model="group.name"
        label="Group Name"
        :rules="nameRules"
        clearable
        autofocus
      />
      <AdminRelationPicker
        :value="group.userSet"
        label="Users"
        :items="vuetifyUsers"
        @change="group.userSet = $event"
      />
      <AdminRelationPicker
        :value="group.librarySet"
        label="Libraries"
        :items="vuetifyLibraries"
        @change="group.librarySet = $event"
      />
      <AdminSubmitFooter
        :verb="verb"
        table="Group"
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
import AdminSubmitFooter from "@/components/submit-footer.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["name", "userSet", "librarySet"];
const EMPTY_GROUP = {
  name: "",
  userSet: [],
  librarySet: [],
};
Object.freeze(EMPTY_GROUP);

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminGroupCreateUpdateDialog",
  components: {
    AdminRelationPicker,
    AdminCreateUpdateButton,
    AdminSubmitFooter,
  },
  props: {
    update: { type: Boolean, default: false },
    oldGroup: {
      type: Object,
      default: () => {
        return { ...EMPTY_GROUP };
      },
    },
  },
  data() {
    return {
      nameRules: [
        (v) => !!v || "Name is required",
        (v) => (!!v && !this.names.has(v.trim())) || "Name is already used",
      ],
      group: { ...EMPTY_GROUP },
      showDialog: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      names: function (state) {
        const names = new Set();
        for (const group of state.groups) {
          if (!this.update || group.name !== this.oldGroup.name) {
            names.add(group.name);
          }
        }
        return names;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyLibraries", "vuetifyUsers"]),
    submitButtonDisabled: function () {
      let changed = false;
      for (const [key, value] of Object.entries(this.group)) {
        if (this.oldGroup[key] !== value) {
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
  },
  verb() {
    return this.update ? "Update" : "Add";
  },
  watch: {
    showDialog(show) {
      this.group =
        show && this.update ? this.createUpdateGroup() : { ...EMPTY_GROUP };
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["createRow", "updateRow"]),
    createUpdateGroup() {
      const updateGroup = {};
      for (const key of UPDATE_KEYS) {
        updateGroup[key] = this.oldGroup[key];
      }
      return updateGroup;
    },
    doUpdate: function () {
      const updateGroup = {};
      for (const [key, value] of Object.entries(this.group)) {
        if (this.oldGroup[key] !== value) {
          updateGroup[key] = value;
        }
      }
      this.updateRow("Group", this.oldGroup.pk, updateGroup)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    doCreate: function () {
      this.createRow("Group", this.group)
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
