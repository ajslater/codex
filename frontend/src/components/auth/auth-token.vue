<template>
  <v-dialog
    v-if="user"
    v-model="showAuthTokenDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="24em"
  >
    <template #activator="{ props }">
      <CodexListItem
        :prepend-icon="mdiTicketConfirmationOutline"
        v-bind="props"
        title="Auth Token"
      />
    </template>
    <div id="tokenDialog">
      <h2>Auth Token</h2>
      <ClipBoard
        class="tokenContainer"
        :tooltip="TOOLTIP"
        :title="title"
        :text="token"
      />
      <v-btn @click.stop="resetToken">Reset Token</v-btn>
    </div>
  </v-dialog>
</template>

<script>
import { mdiTicketConfirmationOutline } from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import ClipBoard from "@/components/clipboard.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAuthStore } from "@/stores/auth";

const TOOLTIP = "Copy Auth Token to clipboard";

export default {
  name: "AuthTokenDialog",
  components: {
    ClipBoard,
    CodexListItem,
  },
  props: {
    user: { type: Object, required: true },
  },
  data() {
    return {
      mdiTicketConfirmationOutline,
      showTooltip: { show: false },
      TOOLTIP,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["token"]),
    ...mapWritableState(useAuthStore, ["showAuthTokenDialog"]),
    title() {
      return `User: ${this.user.username}`;
    },
    tooltip() {
      return this.clipBoardEnabled ? TOOLTIP : undefined;
    },
  },
  methods: {
    ...mapActions(useAuthStore, ["getToken", "updateToken"]),
    resetToken() {
      this.updateToken();
      this.showTooltip.show = false;
    },
  },
  created() {
    this.getToken();
  },
};
</script>

<style scoped lang="scss">
#tokenDialog {
  padding: 20px;
  text-align: center;
}

.tokenContainer {
  padding-top: 1em;
  padding-bottom: 1em;
  text-align: left;
}
</style>
