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
      <AdminFailedImportsPanel />
    </v-expand-transition>
    <p class="adminProse libraryHelp">
      Each Watched File Events box checked creates a thread to monitor the
      Library. An large number of watching threads may exceed the limits of your
      operating system or container.
    </p>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminFailedImportsPanel from "@/components/admin/tabs/failed-imports-panel.vue";
import AdminLibraryTable from "@/components/admin/tabs/library-table.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminFailedImportsPanel,
    AdminLibraryTable,
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
    this.loadTables(["Group", "Library", "FailedImport"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTables"]),
  },
};
</script>
<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.libraryHelp {
  margin-top: 2em;
}
</style>
