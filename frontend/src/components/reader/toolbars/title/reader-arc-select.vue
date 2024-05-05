<template>
  <ToolbarSelect
    v-model="arc"
    class="arcSelect"
    select-label="order"
    :items="arcItems"
    :disabled="!arcItems || arcItems.length <= 1"
  >
    <template #item="{ item, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :prepend-icon="arcIcon(item.raw.group)"
        :subtitle="arcLabel(item.raw.group)"
        :append-icon="checkIcon(props.value)"
      />
    </template>
    <template #selection="{ item, props }">
      <v-icon size="large" v-bind="props" class="arcSelectIcon">
        {{ arcIcon(item.raw.group) }}
      </v-icon>
    </template>
  </ToolbarSelect>
</template>
<script>
import { mdiBookMultiple, mdiCheck, mdiFolderOutline, mdiRedo } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbars/toolbar-select.vue";
import { useReaderStore } from "@/stores/reader";

const ARC_ICONS = {
  a: mdiRedo,
  f: mdiFolderOutline,
  s: mdiBookMultiple,
};

const LABELS = {
  a: "Story Arc",
  f: "Folder",
  s: "Series",
};

export default {
  name: "ReaderArcSelect",
  components: {
    ToolbarSelect,
  },
  computed: {
    ...mapState(useReaderStore, {
      arcGroup: (state) => state.arc?.group || "s",
      arcName: (state) => {
        for (const arc of state.arcs) {
          if (state.arc.group === arc.group && state.arc.pk === arc.pk) {
            return arc.name;
          }
        }
        return "Unknown";
      },
      arcKey: (state) => `${state.arc.group}:${state.arc.pk}`,
      arcItems: (state) => {
        const items = [];
        for (const arc of state.arcs) {
          const item = {
            value: `${arc.group}:${arc.pk}`,
            title: arc.name,
            group: arc.group,
          };
          items.push(item);
        }
        return items;
      },
    }),
    arc: {
      get() {
        return this.arcKey;
      },
      set(arcKey) {
        const routeParams = this.$route.params;
        if (!routeParams) {
          return;
        }
        const [arcGroup, arcPk] = arcKey.split(":");
        const params = {
          ...routeParams,
          arcGroup,
          arcPk,
        };
        this.loadBooks(params);
      },
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["loadBooks"]),
    arcIcon(group) {
      return ARC_ICONS[group];
    },
    arcLabel(group) {
      return LABELS[group];
    },
    checkIcon(value) {
      return value === this.arc ? mdiCheck : "";
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-select__selection) {
  color: rgb(var(--v-theme-textSecondary)) !important;
}
:deep(.v-select__selection .arcSelectIcon) {
  top: 4px;
  color: rgb(var(--v-theme-textSecondary));
}
:deep(.v-select__selection:hover) .arcSelectIcon {
  color: white;
}
:deep(.v-list-item__spacer) {
  max-width: 12px; 
}
</style>
