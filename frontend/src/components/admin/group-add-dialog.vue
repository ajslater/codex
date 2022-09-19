<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn ripple rounded v-on="on"> + Add Group </v-btn>
    </template>
    <v-form id="groupAddDialog" ref="form">
      <v-text-field
        v-model="group.name"
        label="Group Name"
        :rules="nameRules"
        clearable
        autofocus
        @keydown.enter="$refs.addGroup.focus()"
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
      <v-btn
        ref="addGroup"
        ripple
        :disabled="!addGroupButtonEnabled"
        @click="addGroup"
      >
        Add Group
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

const EMPTY_GROUP = {
  name: "",
  userSet: [],
  librarySet: [],
};
Object.freeze(EMPTY_GROUP);

export default {
  name: "AdminGroupAddDialog",
  components: {
    AdminRelationPicker,
  },
  data() {
    return {
      nameRules: [
        (v) => !!v || "Name is required",
        (v) =>
          (!!v && !this.names.includes(v.trim())) || "Name is already used",
      ],
      group: { ...EMPTY_GROUP },
      showDialog: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      formErrors: (state) => state.errors,
      formSuccess: (state) => state.success,
      names: (state) => {
        const groupNames = [];
        for (const group of state.groups) {
          groupNames.push(group.name);
        }
        return groupNames;
      },
    }),
    ...mapGetters(useAdminStore, ["vuetifyLibraries", "vuetifyUsers"]),
    addGroupButtonEnabled: function () {
      for (const rule of this.nameRules) {
        if (rule(this.group.name) !== true) {
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
    addGroup: function () {
      const form = this.$refs.form;
      if (!form.validate()) {
        return;
      }
      this.createRow("Group", this.group)
        .then(() => {
          this.showDialog = false;
          this.group = { ...EMPTY_GROUP };
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
#groupAddDialog {
  padding: 20px;
}
</style>
