<template>
  <ToolbarSelect
    :model-value="arc"
    class="arcSelect"
    select-label="reading order"
    :items="items"
    :disabled="!items || items.length <= 1"
    @update:model-value="onUpdate"
  >
    <template #item="{ item, props }">
      <v-list-item
        v-bind="props"
        density="compact"
        variant="plain"
        :prepend-icon="item.raw.prependIcon"
        :subtitle="item.raw.subtitle"
        :append-icon="item.raw.appendIcon"
      />
    </template>
    <template #selection="{ props }">
      <v-icon
        :icon="prependIcon(arc.group)"
        size="large"
        v-bind="props"
        class="arcSelectIcon"
      />
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

import { topGroup as GROUP_LABELS } from "@/choices/browser-map";
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
      arc: (state) => state.arc,
      arcs: (state) => state.arcs,
    }),
    items() {
      const items = [];
      if (!this.arcs) {
        return items;
      }
      for (const [group, arcIdsInfo] of Object.entries(this.arcs)) {
        for (const [ids, arcInfo] of Object.entries(arcIdsInfo)) {
          let subtitle = GROUP_LABELS[group];
          if (group !== "s") {
            subtitle = subtitle.slice(0, -1);
          }
          const prependIcon = ARC_ICONS[group];
          const appendIcon =
            group === this.arc?.group && ids == this.arc?.ids ? mdiCheck : "";
          const value = { group, ids, prependIcon, ...arcInfo };
          const item = {
            group,
            value,
            title: arcInfo.name,
            subtitle,
            prependIcon,
            appendIcon,
          };
          items.push(item);
        }
      }
      return items;
    },
    arcInfo() {
      if (!this.arcs || !this.arc) {
        return {};
      }
      const arcIdsInfo = this.arcs[this.arc?.group];
      if (!arcIdsInfo) {
        return {};
      }
      return arcIdsInfo[this.arc?.ids];
    },
    arcIcon() {
      return ARC_ICONS[this.arc?.group];
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["loadBooks"]),
    onUpdate(item) {
      const arc = {
        group: item.group,
        ids: item.ids.split(",").map(Number),
      };
      this.loadBooks({ arc });
    },
    prependIcon(group) {
      return ARC_ICONS[group];
    },
  },
};
</script>

<style scoped lang="scss">
.arcSelect {
  min-width: 79px;
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
