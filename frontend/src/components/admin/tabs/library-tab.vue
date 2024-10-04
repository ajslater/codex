<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
      />
    </header>
    <AdminLibraryTable
      :items="normalLibraries"
      :sort-by="[{ key: 'path', order: 'asc' }]"
    />

    <v-expand-transition>
      <AdminFailedImportsPanel id="failedImports" />
    </v-expand-transition>

    <v-expand-transition>
      <AdminCustomCoversPanel id="customCovers" />
    </v-expand-transition>
  </div>
</template>

<script>
import { mapActions, mapGetters } from "pinia";
import { markRaw } from "vue";

import AdminCreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminCustomCoversPanel from "@/components/admin/tabs/custom-covers-panel.vue";
import AdminFailedImportsPanel from "@/components/admin/tabs/failed-imports-panel.vue";
import AdminLibraryTable from "@/components/admin/tabs/library-table.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminFailedImportsPanel,
    AdminLibraryTable,
    AdminCreateUpdateDialog,
    AdminCustomCoversPanel,
  },
  data() {
    return {
      AdminLibraryCreateUpdateInputs: markRaw(AdminLibraryCreateUpdateInputs),
    };
  },
  computed: {
    ...mapGetters(useAdminStore, ["normalLibraries"]),
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
#customCovers {
  margin-top: 60px;
}
</style>
