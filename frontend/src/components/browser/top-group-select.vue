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
      <v-divider v-if="DIVIDED_VALUES.has(item.value)" />
      <v-list-item v-bind="props" :title="item.title" :value="item.value" />
    </template>
  </ToolbarSelect>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

const FOLDER_ROUTE = { params: { group: "f", pk: 0, page: 1 } };
const DIVIDED_VALUES = new Set(["a", "f"]);

export default {
  name: "BrowserTopGroupSelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  data() {
    return {
      FOLDER_ROUTE,
      DIVIDED_VALUES,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      topGroupSetting: (state) => state.settings.topGroup,
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
        const group = DIVIDED_VALUES.has(value) ? value : "r";
        const topRoute = {
          params: { group, pk: 0, page: 1 },
        };
        const settings = { topGroup: value };
        this.$router
          .push(topRoute)
          .then(() => {
            return this.setSettings(settings);
          })
          .catch(console.error);
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
