<template>
  <v-snackbar
    v-model="show"
    color="warning"
    timeout="-1"
    location="top"
    multi-line
    vertical
  >
    <div id="dockerHubTitle">Docker Hub image deprecated</div>
    <div>
      Codex images are now published only at ghcr.io. The
      <code class="dockerHubImage">docker.io/ajslater/codex</code> image will
      stop receiving updates. Change this container's image to
      <code class="dockerHubImage">ghcr.io/ajslater/codex</code> and recreate
      it. The tags are the same, and your config and comics volumes carry over
      unchanged.
    </div>
    <template #actions>
      <v-btn variant="text" :href="DOCKER_DOCS_URL" target="_blank">
        How to switch
      </v-btn>
      <v-btn variant="text" @click="dismiss"> Dismiss </v-btn>
    </template>
  </v-snackbar>
</template>
<script>
import { mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";

const DOCKER_DOCS_URL =
  "https://codex-comic-reader.readthedocs.io/DOCKER/#migrating-from-docker-hub";
/*
 * Dismissing hides the warning for a day, per browser. It has to come
 * back: the point is to nag until the image is actually changed.
 */
const DISMISSED_KEY = "codex-docker-hub-warning-dismissed";
const DISMISS_MS = 24 * 60 * 60 * 1000;

const readDismissedAt = () => {
  try {
    return Number(globalThis.localStorage.getItem(DISMISSED_KEY)) || 0;
  } catch {
    // Private mode or blocked storage: never dismissed.
    return 0;
  }
};

const writeDismissedAt = (value) => {
  try {
    globalThis.localStorage.setItem(DISMISSED_KEY, String(value));
  } catch {
    // Storage unavailable; the warning returns on the next page load.
  }
};

export default {
  name: "DockerHubDeprecatedSnackbar",
  data() {
    return {
      DOCKER_DOCS_URL,
      dismissedAt: readDismissedAt(),
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useAuthStore, {
      /*
       * ``/session`` carries the version dict on every route at boot.
       * ``dockerHub`` is set only inside the deprecated Docker Hub image,
       * so ghcr.io and native installs never render this.
       */
      dockerHub: (state) => Boolean(state.version?.dockerHub),
    }),
    recentlyDismissed() {
      return Date.now() - this.dismissedAt < DISMISS_MS;
    },
    show: {
      get() {
        return (
          Boolean(this.isUserAdmin) && this.dockerHub && !this.recentlyDismissed
        );
      },
      set(value) {
        if (!value) {
          this.dismiss();
        }
      },
    },
  },
  methods: {
    dismiss() {
      this.dismissedAt = Date.now();
      writeDismissedAt(this.dismissedAt);
    },
  },
};
</script>
<style scoped lang="scss">
#dockerHubTitle {
  font-weight: bold;
  margin-bottom: 0.5em;
}
.dockerHubImage {
  font-family: monospace;
  user-select: all;
}
</style>
