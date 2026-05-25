<template>
  <div>
    <AdminTable :headers="headers" :items="customCovers">
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          No custom covers yet. Upload one from a card's action menu.
        </td>
      </template>
      <template #[`item.thumb`]="{ item }">
        <img alt="cover" class="customCoverThumb" :src="thumbSrc(item)" />
      </template>
      <template #[`item.group`]="{ item }">
        <v-chip class="groupChip" size="small" variant="tonal">
          {{ item.groupLabel }}
        </v-chip>
      </template>
      <template #[`item.linkedGroupName`]="{ item }">
        <span :class="{ unlinked: !item.linkedGroupName }">
          {{ item.linkedGroupName || "— unlinked —" }}
        </span>
      </template>
      <template #[`item.mtime`]="{ item }">
        <DateTimeColumn :dttm="mtimeIso(item.mtime)" />
      </template>
      <template #[`item.sizeBytes`]="{ item }">
        {{ formatSize(item.sizeBytes) }}
      </template>
      <template #[`item.actions`]="{ item }">
        <AdminDeleteRowDialog
          density="compact"
          :name="item.path"
          :pk="item.pk"
          size="small"
          table="CustomCover"
        />
      </template>
    </AdminTable>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import { useAdminStore } from "@/stores/admin";

const SIZE_UNITS = Object.freeze(["B", "KB", "MB", "GB"]);

export default {
  name: "AdminCustomCoversTab",
  components: { AdminTable, AdminDeleteRowDialog, DateTimeColumn },
  computed: {
    ...mapState(useAdminStore, ["customCovers"]),
    headers() {
      return [
        { title: "", key: "thumb", sortable: false },
        { title: "Group", key: "group" },
        { title: "Linked To", key: "linkedGroupName" },
        { title: "Modified", key: "mtime" },
        { title: "Size", key: "sizeBytes" },
        { title: "Actions", key: "actions", sortable: false },
      ];
    },
  },
  mounted() {
    this.loadTable("CustomCover");
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
    thumbSrc(item) {
      const base = globalThis.CODEX.API_V3_PATH;
      return `${base}custom_cover/${item.pk}/cover.webp?ts=${item.mtime ?? 0}`;
    },
    mtimeIso(mtime) {
      if (!mtime) return undefined;
      return new Date(mtime * 1000).toISOString();
    },
    formatSize(bytes) {
      if (!bytes && bytes !== 0) return "";
      let n = bytes;
      let unit = 0;
      while (n >= 1024 && unit < SIZE_UNITS.length - 1) {
        n /= 1024;
        unit += 1;
      }
      const formatted = unit === 0 ? n.toString() : n.toFixed(1);
      return `${formatted} ${SIZE_UNITS[unit]}`;
    },
  },
};
</script>

<style scoped lang="scss">
.customCoverThumb {
  width: 60px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
}

.groupChip {
  text-transform: uppercase;
}

.unlinked {
  color: rgb(var(--v-theme-textDisabled));
  font-style: italic;
}
</style>
