<template>
  <v-menu location="end">
    <template #activator="{ props }">
      <v-list-item
        v-bind="props"
        class="exportListItem"
        :append-icon="mdiChevronRight"
        title="Export"
      />
    </template>
    <v-list density="compact">
      <v-list-item
        v-for="fmt in EXPORT_FORMATS"
        :key="fmt.value"
        :title="fmt.title"
        :href="exportURL(pk, fmt.value)"
        download
      />
    </v-list>
  </v-menu>
</template>

<script>
import { mdiChevronRight } from "@mdi/js";

import { exportURL } from "@/api/v4/reading-lists";
import { EXPORT_FORMATS } from "@/stores/reading-lists";

/*
 * A list's Export entry: a submenu of the formats it downloads as, for
 * the menus of the admin table and the settings drawer.
 */
export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "ReadingListExportMenu",
  props: {
    pk: { type: Number, required: true },
  },
  data() {
    return { EXPORT_FORMATS, mdiChevronRight };
  },
  methods: {
    exportURL,
  },
};
</script>
