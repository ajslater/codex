<template>
  <v-dialog
    v-model="showAuthTokenDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="32em"
  >
    <template #activator="{ props }">
      <CodexListItem
        :prepend-icon="mdiTicketConfirmationOutline"
        v-bind="props"
        title="Auth Token"
      />
    </template>
    <div id="tokenDialog">
      <h2>
        Auth Token<br />
        for {{ username }}
      </h2>
      <ClipBoard
        class="tokenContainer"
        :tooltip="TOOLTIP"
        title="Token"
        :text="token"
      />
      <div id="bearerTokenHelp">
        <h3>Custom Headers</h3>
        <p>
          If your client doesn't have a dedicated Bearer token settings feature
          but allows custom headers you can set the authorization header
          manually:
        </p>
        <table id="bearerTokenHelpTable">
          <tbody>
            <tr>
              <td>Key</td>
              <td class="helpValue">Authorization</td>
            </tr>
            <tr>
              <td>Value</td>
              <td class="helpValue">Bearer {{ token }}</td>
            </tr>
          </tbody>
        </table>
      </div>
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
      username: this.user.username,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["token"]),
    ...mapWritableState(useAuthStore, ["showAuthTokenDialog"]),
    title() {
      return `For user: ${this.username}`;
    },
    tooltip() {
      return this.clipBoardEnabled ? TOOLTIP : undefined;
    },
  },
  created() {
    this.getToken();
  },
  methods: {
    ...mapActions(useAuthStore, ["getToken", "updateToken"]),
    resetToken() {
      this.updateToken();
      this.showTooltip.show = false;
    },
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

h3 {
  color: white;
}

#bearerTokenHelp {
  text-align: left;
  color: rgb(var(--v-theme-textDisabled));
  padding-bottom: 1em;
  max-width: 29em;
}

#bearerTokenHelp td {
  padding: 4px;
}

.helpValue {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
}
</style>
