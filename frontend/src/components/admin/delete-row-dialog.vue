<template>
  <v-dialog
    orign="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn icon ripple v-on="on">
        <v-icon> {{ mdiTrashCan }} </v-icon>
      </v-btn>
    </template>
    <div id="deleteDialog">
      Delete {{ table }} {{ name }}?
      <v-btn id="confirmButton" @click="deleteRow"> Confirm Delete </v-btn>
    </div>
  </v-dialog>
</template>

<script>
import { mdiTrashCan } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminDeleteRowDialog",
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
  emits: ["deleted"],
  data() {
    return {
      showDeleteRowDialog: false,
      mdiTrashCan,
    };
  },
  computed: {
    ...mapState(useAdminStore, {}),
  },
  methods: {
    ...mapActions(useAdminStore, ["deleteRow"]),
    deleteRow: async function () {
      const adminStore = useAdminStore();
      adminStore.deleteRow(this.table, this.pk).catch((error) => {
        console.warn(error);
      });
    },
  },
};
</script>

<style scoped lang="scss">
#deleteDialog {
  padding: 20px;
  text-align: center;
  background-color: #272727;
}
#confirmButton {
  margin-top: 1em;
}
</style>
