<template>
  <v-dialog v-model="showApiAccessDialog" max-width="640" scrollable>
    <!-- The card gives the overlay an intrinsic size. Without it the
       body is a shrink-to-fit box, and a percentage-sized placeholder
       inside one resolves to nothing: the dialog opens as an invisible
       sliver behind the scrim, which reads as "no window appeared". -->
    <v-card id="apiAccess">
      <v-card-text class="apiAccessBody">
        <h2 class="apiAccessTitle">
          <v-icon class="apiAccessIcon">{{ mdiRss }}</v-icon>
          API Access
        </h2>
        <ApiUrls v-if="apiUrls" :urls="apiUrls" :username="username" />
        <div v-else-if="apiUrlsError" class="apiAccessError">
          <p>{{ apiUrlsError }}</p>
          <v-btn variant="text" text="Retry" @click="loadApiUrls" />
        </div>
        <div v-else class="apiAccessLoading">
          <PlaceholderLoading :size="64" />
        </div>
        <ApiKeys v-if="user" :urls="apiUrls || EMPTY_URLS" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn text="Close" @click="showApiAccessDialog = false" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mdiRss } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import ApiKeys from "@/components/api-access/api-keys.vue";
import ApiUrls from "@/components/api-access/api-urls.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useAuthStore } from "@/stores/auth";

const EMPTY_URLS = Object.freeze({});

export default {
  name: "ApiAccessDialog",
  components: {
    ApiKeys,
    ApiUrls,
    PlaceholderLoading,
  },
  data() {
    return { EMPTY_URLS, mdiRss };
  },
  computed: {
    ...mapState(useAuthStore, ["apiUrls", "apiUrlsError", "user"]),
    ...mapWritableState(useAuthStore, ["showApiAccessDialog"]),
    username() {
      return this.user?.username || "";
    },
  },
  watch: {
    showApiAccessDialog: {
      handler(open) {
        if (!open) {
          return;
        }
        // Every open: an admin may have turned an API on or off since.
        this.loadApiUrls();
        if (this.user) {
          this.loadApiKeys();
        }
      },
      immediate: true,
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["loadApiKeys", "loadApiUrls"]),
  },
};
</script>

<style scoped lang="scss">
.apiAccessBody {
  display: flex;
  flex-direction: column;
  gap: 1em;
}

.apiAccessTitle {
  margin: 0;
}

.apiAccessIcon {
  display: inline-flex;
  vertical-align: -4px;
  font-size: 25px;
}

.apiAccessError {
  text-align: center;
}

.apiAccessLoading {
  display: flex;
  justify-content: center;
  min-height: 144px;
  padding: 40px;
}
</style>
