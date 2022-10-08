<template>
  <ConfirmDialog
    :icon="mdiTrashCan"
    :title-text="titleText"
    :object-name="name"
    :confirm-text="titleText"
    @confirm="confirm"
  />
</template>

<script>
import { mdiTrashCan } from "@mdi/js";
import { mapActions } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminDeleteRowDialog",
  components: {
    ConfirmDialog,
  },
  props: {
    table: {
      type: String,
      required: true,
    },
    pk: {
      type: Number,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      mdiTrashCan,
    };
  },
  computed: {
    titleText() {
      return `Delete ${this.table}`;
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["deleteRow"]),
    confirm() {
      this.deleteRow(this.table, this.pk);
      this.showDialog = false;
    },
  },
};
</script>
