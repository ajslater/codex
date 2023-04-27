<template>
  <v-dialog max-width="30em">
    <template #activator="{ props }">
      <v-btn id="opdsButton" icon size="small" variant="plain" v-bind="props">
        <v-icon>{{ mdiRss }}</v-icon>
        OPDS
      </v-btn>
    </template>
    <div id="opds">
      <h2>
        <v-icon size="x=small" class="inline">{{ mdiRss }}</v-icon>
        OPDS
      </h2>
      <OPDSUrl title="v1.2" :url="opdsV1URL" />
      <OPDSUrl
        title="v2.0"
        :url="opdsV2URL"
        subtitle="OPDS v2 is experimental and not widely or well supported by clients"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiRss } from "@mdi/js";

import OPDSUrl from "@/components/settings/opds-url.vue";

export default {
  name: "OPDSDialog",
  components: {
    OPDSUrl,
  },
  data() {
    return {
      mdiRss,
      opdsV1URL: window.origin + window.CODEX.OPDS_V1_PATH,
      opdsV2URL: window.origin + window.CODEX.OPDS_V2_PATH,
    };
  },
};
</script>
<style scoped lang="scss">
#opds {
  padding: 20px;
}
#opdsButton {
  color: rgb(var(--v-theme-textSecondary));
}
.inline {
  display: inline-flex;
}
</style>
