<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
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
      <footer>
        <v-btn id="confirmButton" @click="deleteRow"> Confirm Delete </v-btn>
        <CancelButton @click="showDialog = false" />
      </footer>
    </div>
  </v-dialog>
</template>

<script>
import { mdiTrashCan } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import CancelButton from "@/components/cancel-button.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminDeleteRowDialog",
  components: {
    CancelButton,
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
  emits: ["deleted"],
  data() {
    return {
      showDialog: false,
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
}
footer {
  margin: auto;
  margin-top: 1em;
  display: flex;
  justify-content: space-between;
}
</style>
