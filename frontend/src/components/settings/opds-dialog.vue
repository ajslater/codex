<template>
  <v-dialog max-width="480">
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
    <!-- The card gives the overlay an intrinsic size. Without it the
       body is a shrink-to-fit box, and a percentage-sized placeholder
       inside one resolves to nothing: the dialog opens as an invisible
       sliver behind the scrim, which reads as "no window appeared". -->
    <v-card>
      <div v-if="opdsURLs" id="opds">
        <h2 id="opdsTitle">
          <v-icon id="opdsIcon">
            {{ mdiRss }}
          </v-icon>
          OPDS
        </h2>
        <OPDSUrl title="v1.2" :url-path="opdsURLs.v1" />
        <OPDSUrl
          title="v2.0"
          :url-path="opdsURLs.v2"
          subtitle="Supported in newer clients (like Stump)"
        />
      </div>
      <div v-else-if="opdsURLsError" id="opdsError">
        <p>{{ opdsURLsError }}</p>
        <v-btn variant="text" @click="loadOPDSURLs"> Retry </v-btn>
      </div>
      <div v-else id="opdsLoading">
        <PlaceholderLoading :size="64" />
      </div>
    </v-card>
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
      opdsURLsError: (state) => state.opdsURLsError,
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

#opdsTitle {
  margin-top: 0px;
}

#opdsButton {
  display: block;
  width: 100%;
  color: rgb(var(--v-theme-text-secondary));
}

#opdsIcon {
  display: inline-flex;
  vertical-align: -4px;
  font-size: 25px;
}

#opdsError {
  padding: 20px;
  text-align: center;
}

#opdsLoading {
  display: flex;
  justify-content: center;
  padding: 40px;
}
</style>
