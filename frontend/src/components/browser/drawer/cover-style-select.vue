<template>
  <v-select
    class="coverStyleSelect"
    :model-value="coverStyle"
    label="Group Cover Style"
    density="compact"
    variant="plain"
    flat
    :items="coverStyleChoices"
    hide-details
    @update:model-value="setCoverStyle($event)"
  >
    <template #item="{ item, props }">
      <v-list-item
        class="coverStyleItem"
        v-bind="props"
        density="compact"
        variant="plain"
        :prepend-icon="COVER_STYLE_ICONS[item.raw.value]"
        :title="item.raw.title"
      />
    </template>
    <template #selection="{ item, props }">
      <v-list-item
        class="coverStyleSelection"
        v-bind="props"
        density="compact"
        variant="plain"
        :prepend-icon="COVER_STYLE_ICONS[item.raw.value]"
        :title="item.raw.title"
      />
    </template>
  </v-select>
</template>
<script>
import { mdiFilterSettingsOutline, mdiNumeric1CircleOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "CoverStyleSelect",
  data() {
    return {
      COVER_STYLE_ICONS: {
        d: mdiFilterSettingsOutline,
        f: mdiNumeric1CircleOutline,
      },
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      coverStyle: (state) => state.settings.coverStyle,
      coverStyleChoices: (state) => state.choices?.static?.coverStyle || [],
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setCoverStyle(value) {
      const data = { coverStyle: value };
      this.setSettings(data);
    },
  },
};
</script>
<style scoped lang="scss">
.coverStyleSelect {
  padding-left: 18px;
  padding-top: 10px;
  padding-bottom: 2px;
}
.coverStyleSelection { 
  padding-left: 0px;
  opacity: 1;
}
.coverStyleSelection :deep(.v-list-item__spacer),
.coverStyleItem :deep(.v-list-item__spacer)
{
  display: none;
}
.coverStyleSelection :deep(.v-icon),
.coverStyleItem :deep(.v-icon) {
  margin-right: 0.33em;
}
</style>
