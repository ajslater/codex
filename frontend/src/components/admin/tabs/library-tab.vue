<template>
  <div>
    <header class="tabHeader">
      <AdminCreateUpdateDialog
        table="Library"
        :inputs="AdminLibraryCreateUpdateInputs"
      />
    </header>
    <AdminLibraryTable
      :items="libraryItems"
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
import { mapActions, mapState } from "pinia";
import { markRaw } from "vue";

import AdminLibraryCreateUpdateInputs from "@/components/admin/create-update-dialog/library-create-update-inputs.vue";
import AdminCustomCoversPanel from "@/components/admin/tabs/custom-covers-panel.vue";
import AdminFailedImportsPanel from "@/components/admin/tabs/failed-imports-panel.vue";
import AdminLibraryTable from "@/components/admin/tabs/library-table.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminLibrariesTab",
  components: {
    AdminLibraryTable,
    AdminFailedImportsPanel,
    AdminCustomCoversPanel,
  },
  data() {
    return {
      AdminLibraryCreateUpdateInputs: markRaw(AdminLibraryCreateUpdateInputs),
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      libraryItems(state) {
        const annotatedItems = [];
        for (const library of state.libraries) {
          if (!library.coversOnly) {
            const annotatedItem = { ...library };
            annotatedItem.label = annotatedItem.coversOnly
              ? "custom group cover"
              : "comic";
            annotatedItems.push(annotatedItem);
          }
        }
        return annotatedItems;
      },
    }),
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
