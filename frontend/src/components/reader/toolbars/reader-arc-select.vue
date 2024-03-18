<template>
  <v-select
    v-if="arcItems.length > 1"
    v-model="arc"
    class="arcSelect"
    density="compact"
    hide-details="auto"
    label="Order"
    variant="plain"
    :items="arcItems"
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
      <v-list-item v-bind="props" density="compact" variant="plain">
        <v-icon>
          {{ arcIcon(item.raw.group) }}
        </v-icon>
      </v-list-item>
    </template>
  </v-select>
  <v-icon v-else id="onlyArc" :title="arcName">
    {{ arcIcon(arcGroup) }}
  </v-icon>
  <span v-if="arcPosition" id="arcPosition">{{ arcPosition }}</span>
</template>
<script>
import { mdiBookMultiple, mdiCheck, mdiFolderOutline, mdiRedo } from "@mdi/js";
import { mapActions, mapState } from "pinia";

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
      arcPosition: function (state) {
        const arc = state.arc;
        if (arc && arc.index && arc.count) {
          return `${arc.index}/${arc.count}`;
        }
        return "";
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
@use "vuetify/styles/settings/variables" as vuetify;
// Lower label from out of bounds
::v-deep(.v-label.v-field-label) {
  top: 13px;
}
// Compact input spacing
::v-deep(.v-field__input) {
  padding-right: 0;
}
// Compact list item spacing
::v-deep(.v-list-item) {
  padding: 0;
}
::v-deep(.v-list-item__prepend) {
  display: block;
  width: 24px !important;
  margin-right: 5px;
}
::v-deep(.v-select__menu-icon) {
  margin: 0;
}
#onlyArc {
  margin-top: 13px;
  color: rgb(var(--v-theme-textSecondary));
}
// Arc Position
#arcPosition {
  padding-top: 13px;
  padding-left: 10px;
  padding-right: 10px;
  color: rgb(var(--v-theme-textSecondary));
  text-align: center;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #arcPosition {
    padding-left: 0px;
    padding-right: 0px;
  }
}
</style>
