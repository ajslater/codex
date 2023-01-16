<template>
  <ToolbarSelect
    v-bind="$attrs"
    v-model="topGroup"
    class="topGroupSelect"
    select-label="top group"
    :items="topGroupChoices"
    :max-select-len="topGroupChoicesMaxLen - 1"
    :mobile-len-adj="-2.5"
  >
    <template #item="{ item, props }">
      <!-- Divider in items not implemented yet in Vuetify 3 -->
      <v-divider v-if="item.value === 'f'" />
      <v-list-item v-bind="props" :title="item.title" :value="item.value" />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

const FOLDER_ROUTE = { params: { group: "f", pk: 0, page: 1 } };

export default {
  name: "BrowserTopGroupSelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  data() {
    return {
      FOLDER_ROUTE,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      topGroupSetting: (state) => state.settings.topGroup,
      enableFolderView: (state) => state.page.adminFlags.enableFolderView,
    }),
    ...mapGetters(useBrowserStore, [
      "topGroupChoices",
      "topGroupChoicesMaxLen",
    ]),
    topGroup: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        const settings = { topGroup: value };
        if (
          (this.topGroupSetting === "f" && value !== "f") ||
          (this.topGroupSetting !== "f" && value === "f")
        ) {
          // Change major views
          const group = value === "f" ? "f" : "r";
          const topRoute = {
            params: { group, pk: 0, page: 1 },
          };
          this.$router
            .push(topRoute)
            .then(() => {
              return this.setSettings(settings);
            })
            .catch(console.error);
        } else {
          // Change group style top group
          this.setSettings(settings);
        }
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

<style scoped lang="scss">
:deep(.v-field-label--floating) {
  padding-left: calc(env(safe-area-inset-left) / 3);
}
</style>
