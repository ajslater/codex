<template>
  <v-dialog
    v-model="showDialog"
    transition="scale-transition"
    overlay-opacity="0.5"
    v-bind="$attrs"
    class="cuDialog"
  >
    <template #activator="{ props }">
      <AdminCreateUpdateButton
        :update="Boolean(oldRow)"
        :table="table"
        v-bind="props"
      />
    </template>
    <v-form ref="form" class="cuForm">
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
    };
  },
  computed: {
    submitButtonEnabled: function () {
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
      return form && form.validate();
    },
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
    change(event) {
      this.row = event;
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
      if (!form.validate()) {
        console.warn("submit attempted with invalid form");
        return;
      }
      if (this.oldRow) {
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
  max-height: 100%;
}
</style>
