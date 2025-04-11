<template>
  <ToolbarSelect
    :model-value="arc"
    class="arcSelect"
    select-label="reading order"
    :items="arcItems"
    :disabled="!arcItems || arcItems.length <= 1"
    @update:model-value="onUpdate"
  >
    <template #item="{ item, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :prepend-icon="item.raw.prependIcon"
        :subtitle="subtitle(item.raw)"
        :append-icon="checkIcon(props.value)"
      />
    </template>
    <template #selection="{ item, props }">
      <v-icon size="large" v-bind="props" class="arcSelectIcon">
        {{ arcIcon(item.raw.group) }}
      </v-icon>
      <span id="arcPos"> {{ arc.index }} / {{ arc.count }} </span>
    </template>
  </ToolbarSelect>
</template>
<script>
import {
  mdiBookMultiple,
  mdiBookshelf,
  mdiCheck,
  mdiChessRook,
  mdiFeather,
  mdiFilterOutline,
  mdiFolderOutline,
  mdiRedo,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ToolbarSelect from "@/components/toolbar-select.vue";
import { useReaderStore } from "@/stores/reader";

const ARC_ICONS = {
  a: mdiRedo,
  f: mdiFolderOutline,
  p: mdiChessRook,
  i: mdiFeather,
  s: mdiBookshelf,
  v: mdiBookMultiple,
};

const LABELS = {
  a: "Story Arc",
  f: "Folder",
  p: "Publisher",
  i: "Imprint",
  s: "Series",
  v: "Volume",
};

export default {
  name: "ReaderArcSelect",
  components: {
    ToolbarSelect,
  },
  data() {
    return {
      mdiFilterOutline,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      arcGroup: (state) => state.arc?.group || "s",
      arc: (state) => state.arc,
      arcName: (state) => {
        for (const arc of state.arcs) {
          if (state.arc.group === arc.group && state.arc.pks === arc.pks) {
            return arc.name;
          }
        }
        return "Unknown";
      },
      arcItems: (state) => {
        const items = [];
        for (const arc of state.arcs) {
          const item = {
            value: arc,
            title: arc.name,
            group: arc.group,
            filters: arc.filters,
            subtitle: LABELS[arc.group],
            prependIcon: ARC_ICONS[arc.group],
          };
          items.push(item);
        }
        return items;
      },
    }),
  },
  methods: {
    ...mapActions(useReaderStore, ["loadBooks"]),
    arcIcon(group) {
      return ARC_ICONS[group];
    },
    checkIcon(value) {
      return value.group === this.arc.group && value.pks == this.arc.pks
        ? mdiCheck
        : "";
    },
    subtitle(item) {
      let text = item.subtitle;
      if (item.filters) {
        text += " (filtered)";
      }
      return text;
    },
    onUpdate(selectedArc) {
      const arc = { group: selectedArc.group, pks: selectedArc.pks };
      this.loadBooks({ arc });
    },
  },
};
</script>

<style scoped lang="scss">
.arcSelect {
  min-width: 74px;
}

#arcPos {
  height: 22.75px;
  padding-top: 4px;
  font-size: 16px;
  letter-spacing: -0.15em;
}

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
