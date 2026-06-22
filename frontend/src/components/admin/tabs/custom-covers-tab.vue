<template>
  <div>
    <v-form
      ref="form"
      class="customCoverSettings"
      @submit.prevent="saveMaxUpload"
    >
      <v-text-field
        v-model.number="maxUploadDraft"
        type="number"
        min="1"
        max="2048"
        label="Max upload size (MB)"
        :rules="maxUploadRules"
        density="compact"
        hide-details="auto"
        class="maxUploadField"
      />
      <AdminActionBar
        :saving="saving"
        :save-disabled="!maxUploadChanged"
        :revert-disabled="!maxUploadChanged || saving"
        @revert="resetMaxUpload"
      />
    </v-form>
    <AdminTable :headers="headers" :items="customCovers">
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          No custom covers yet. Upload one from a card's action menu.
        </td>
      </template>
      <template #[`item.thumb`]="{ item }">
        <v-menu
          :close-on-content-click="false"
          location="end center"
          offset="8"
          transition="scale-transition"
          origin="overlap"
        >
          <template #activator="{ props: activator }">
            <img
              v-bind="activator"
              alt="cover"
              class="customCoverThumb"
              :src="thumbSrc(item)"
            />
          </template>
          <template #default="{ isActive }">
            <div class="coverPopup" @mouseleave="isActive.value = false">
              <img alt="cover" :src="thumbSrc(item)" />
            </div>
          </template>
        </v-menu>
      </template>
      <template #[`item.collection`]="{ item }">
        <v-chip class="collectionChip" size="small" variant="tonal">
          {{ item.collectionLabel }}
        </v-chip>
      </template>
      <template #[`item.linkedCollectionName`]="{ item }">
        <span :class="{ unlinked: !item.linkedCollectionName }">
          {{ item.linkedCollectionName || "— unlinked —" }}
        </span>
      </template>
      <template #[`item.mtime`]="{ item }">
        <DateTimeColumn :dttm="mtimeIso(item.mtime)" />
      </template>
      <template #[`item.sizeBytes`]="{ item }">
        {{ formatSize(item.sizeBytes) }}
      </template>
      <template #[`item.actions`]="{ item }">
        <span class="adminActionCell">
          <ReplaceCoverButton
            v-if="item.linkedCollectionPk"
            density="compact"
            :item="item"
            size="small"
          />
          <AdminDeleteRowDialog
            density="compact"
            :name="item.path"
            :pk="item.pk"
            size="small"
            table="CustomCover"
          />
        </span>
      </template>
    </AdminTable>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { V4_BASE } from "@/api/v4/base";
import AdminActionBar from "@/components/admin/tabs/action-bar.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import AdminDeleteRowDialog from "@/components/admin/tabs/delete-row-dialog.vue";
import ReplaceCoverButton from "@/components/admin/tabs/replace-cover-button.vue";
import { useAdminStore } from "@/stores/admin";

const SIZE_UNITS = Object.freeze(["B", "KB", "MB", "GB"]);
const MAX_UPLOAD_FLAG_KEY = "CM";
const MAX_UPLOAD_MIN = 1;
const MAX_UPLOAD_MAX = 2048;

export default {
  name: "AdminCustomCoversTab",
  components: {
    AdminActionBar,
    AdminTable,
    AdminDeleteRowDialog,
    DateTimeColumn,
    ReplaceCoverButton,
  },
  data() {
    return {
      maxUploadDraft: "",
      saving: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, ["customCovers", "flags"]),
    maxUploadFlag() {
      return (this.flags || []).find(
        (flag) => flag.key === MAX_UPLOAD_FLAG_KEY,
      );
    },
    maxUploadMb() {
      const raw = this.maxUploadFlag?.value;
      if (raw === undefined || raw === null || raw === "") return "";
      const n = Number(raw);
      return Number.isFinite(n) ? n : "";
    },
    maxUploadChanged() {
      return String(this.maxUploadDraft) !== String(this.maxUploadMb);
    },
    maxUploadRules() {
      return [
        (v) => {
          const n = Number(v);
          return (
            (Number.isInteger(n) &&
              n >= MAX_UPLOAD_MIN &&
              n <= MAX_UPLOAD_MAX) ||
            `Must be ${MAX_UPLOAD_MIN}–${MAX_UPLOAD_MAX}`
          );
        },
      ];
    },
    headers() {
      return [
        { title: "", key: "thumb", sortable: false },
        { title: "Collection", key: "collection" },
        { title: "Linked To", key: "linkedCollectionName" },
        { title: "Modified", key: "mtime" },
        { title: "Size", key: "sizeBytes" },
        { title: "Actions", key: "actions", sortable: false },
      ];
    },
  },
  watch: {
    maxUploadMb: {
      immediate: true,
      handler(value) {
        this.maxUploadDraft = value;
      },
    },
  },
  mounted() {
    this.loadTables(["CustomCover", "Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable", "loadTables", "updateRow"]),
    resetMaxUpload() {
      this.maxUploadDraft = this.maxUploadMb;
    },
    async saveMaxUpload() {
      const form = this.$refs.form;
      if (form) {
        const { valid } = await form.validate();
        if (!valid) return;
      }
      this.saving = true;
      try {
        await this.updateRow("Flag", MAX_UPLOAD_FLAG_KEY, {
          value: String(this.maxUploadDraft),
        });
      } finally {
        this.saving = false;
      }
    },
    thumbSrc(item) {
      return `${V4_BASE}covers/custom/${item.pk}?ts=${item.mtime ?? 0}`;
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
@use "@/components/admin/tabs/admin-section.scss";

.customCoverSettings {
  margin-bottom: 12px;
}

.maxUploadField {
  max-width: 240px;
}

.customCoverThumb {
  width: 60px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  cursor: zoom-in;
}

.collectionChip {
  text-transform: uppercase;
}

.unlinked {
  color: rgb(var(--v-theme-textDisabled));
  font-style: italic;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/*
 * Cover popup — rendered into the v-menu's teleport target, so the
 * styles live in an unscoped block. Mirrors the browser-table cover
 * popup so the admin custom-cover grid feels the same on hover.
 */
.coverPopup {
  display: block;
  cursor: zoom-out;
}

.coverPopup img {
  display: block;
  max-height: 70vh;
  max-width: 60vw;
  border-radius: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
}
</style>
