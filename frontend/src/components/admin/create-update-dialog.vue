<template>
  <v-dialog v-model="showDialog" transition="scale-transition" v-bind="$attrs">
    <template #activator="{ props }">
      <AdminCreateUpdateButton
        :update="Boolean(oldRow)"
        :table="table"
        v-bind="props"
      />
    </template>
    <v-form ref="form" class="cuForm">
      <h2>{{ table }}</h2>
      <component :is="inputs" :old-row="oldRow" @change="change" />
      <SubmitFooter
        :verb="verb"
        :table="table"
        :disabled="!submitButtonEnabled"
        @submit="submit"
        @cancel="showDialog = false"
      />
    </v-form>
  </v-dialog>
</template>

<script>
import _ from "lodash";
import { mapActions } from "pinia";

import AdminCreateUpdateButton from "@/components/admin/create-update-button.vue";
import SubmitFooter from "@/components/submit-footer.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminCreateUpdateDialog",
  components: {
    AdminCreateUpdateButton,
    SubmitFooter,
  },
  props: {
    table: {
      type: String,
      required: true,
    },
    oldRow: {
      type: [Object, Boolean],
      default: false,
    },
    inputs: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      row: {},
      showDialog: false,
      submitButtonEnabled: false,
    };
  },
  computed: {
    verb() {
      return this.oldRow ? "Update" : "Add";
    },
  },
  watch: {
    showDialog(show) {
      this.row = this.getRow(show);
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["createRow", "updateRow"]),
    validate() {
      let changed = false;
      for (const [key, value] of Object.entries(this.row)) {
        if (!_.isEqual(this.oldRow[key], value)) {
          changed = true;
          break;
        }
      }
      if (!changed) {
        return false;
      }
      const form = this.$refs.form;
      if (!form) {
        return false;
      }
      return form
        .validate()
        .then(({ valid }) => {
          return valid;
        })
        .catch(() => {
          return false;
        });
    },
    change(event) {
      this.row = event;
      this.submitButtonEnabled = this.validate();
    },
    getRow(show) {
      if (!show || !this.oldRow) {
        return _.cloneDeep(this.inputs.EMPTY_ROW);
      }
      const updateRow = {};
      for (const key of this.inputs.UPDATE_KEYS) {
        updateRow[key] = _.cloneDeep(this.oldRow[key]);
      }
      return updateRow;
    },
    doUpdate: function () {
      // only pass diff from old user as update
      const updateRow = {};
      for (const [key, value] of Object.entries(this.row)) {
        if (!_.isEqual(this.oldRow[key], value)) {
          updateRow[key] = value;
        }
      }
      this.updateRow(this.table, this.oldRow.pk, updateRow)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch(console.error);
    },
    doCreate: function () {
      this.createRow(this.table, this.row)
        .then(() => {
          this.showDialog = false;
          return true;
        })
        .catch(console.error);
    },
    submit: function () {
      const form = this.$refs.form;
      if (!form) {
        return;
      }
      form
        .validate()
        .then(({ valid }) => {
          if (!valid) {
            return;
          } else if (this.oldRow) {
            return this.doUpdate();
          } else {
            return this.doCreate();
          }
        })
        .catch(console.warn);
    },
  },
};
</script>

<style scoped lang="scss">
.cuForm {
  padding: 20px;
  max-height: 100%;
  overflow-y: scroll;
}
</style>
