<template>
  <v-dialog max-width="30em">
    <template #activator="{ props }">
      <v-btn
        id="opdsButton"
        icon
        size="small"
        variant="plain"
        v-bind="props"
        @click="loadOPDSURLs"
      >
        <v-icon>{{ mdiRss }}</v-icon>
        OPDS
      </v-btn>
    </template>
    <div v-if="opdsURLs" id="opds">
      <h2>
        <v-icon size="x=small" class="inline">
          {{ mdiRss }}
        </v-icon>
        OPDS
      </h2>
      <OPDSUrl title="v1.2" :url-path="opdsURLs.v1" />
      <OPDSUrl
        title="v2.0"
        :url-path="opdsURLs.v2"
        subtitle="Supported in some newer clients"
      />
    </div>
    <PlaceholderLoading v-else />
  </v-dialog>
</template>
<script>
import { mdiRss } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import PlaceholderLoading from "@/components/placeholder-loading.vue";
import OPDSUrl from "@/components/settings/opds-url.vue";
import { useCommonStore } from "@/stores/common.js";

export default {
  name: "OPDSDialog",
  components: {
    OPDSUrl,
    PlaceholderLoading,
  },
  data() {
    return {
      mdiRss,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      opdsURLs: (state) => state.opdsURLs,
    }),
  },
  methods: {
    ...mapActions(useCommonStore, ["loadOPDSURLs"]),
  },
};
</script>
<style scoped lang="scss">
#opds {
  padding: 20px;
}

#opdsButton {
  display: block;
  width: 100%;
  color: rgb(var(--v-theme-textSecondary));
}

.inline {
  display: inline-flex;
}
</style>
