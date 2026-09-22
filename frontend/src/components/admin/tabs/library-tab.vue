<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
      />
    </header>
    <AdminLibraryTable
      :items="libraries"
      :sort-by="[{ key: 'path', order: 'asc' }]"
    />

    <v-expand-transition>
      <AdminPendingDeletesPanel />
    </v-expand-transition>

    <v-expand-transition>
      <AdminFailedImportsPanel />
    </v-expand-transition>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminFailedImportsPanel from "@/components/admin/tabs/failed-imports-panel.vue";
import AdminLibraryTable from "@/components/admin/tabs/library-table.vue";
import AdminPendingDeletesPanel from "@/components/admin/tabs/pending-deletes-panel.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminFailedImportsPanel,
    AdminLibraryTable,
    AdminPendingDeletesPanel,
    AdminCreateUpdateDialog,
  },
  data() {
    return {
      AdminLibraryCreateUpdateInputs: markRaw(AdminLibraryCreateUpdateInputs),
    };
  },
  computed: {
    ...mapState(useAdminStore, ["libraries"]),
  },
  mounted() {
    this.loadTables(["Group", "Library", "FailedImport", "PendingDelete"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
  },
};
</script>
<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
</style>
