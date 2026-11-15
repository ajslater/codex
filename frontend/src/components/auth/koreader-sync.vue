<template>
  <v-expansion-panels class="koreaderSync">
    <v-expansion-panel value="koreader">
      <v-expansion-panel-title>KOReader Sync</v-expansion-panel-title>
      <v-expansion-panel-text>
        <p class="koreaderHelp">
          In KOReader open Progress sync, set a custom sync server and log in
          with:
        </p>
        <ClipBoard
          class="koreaderValue"
          tooltip="Copy server URL to clipboard"
          title="Server"
          :text="serverURL"
        />
        <table class="koreaderTable">
          <tbody>
            <tr>
              <td>Username</td>
              <td class="helpValue">{{ username }}</td>
            </tr>
            <tr>
              <td>Password</td>
              <td class="helpValue">your Authorization Bearer Token</td>
            </tr>
            <tr>
              <td>Document matching</td>
              <td class="helpValue">
                Binary, or Filename if you edit tags in Codex
              </td>
            </tr>
          </tbody>
        </table>
        <p class="koreaderHelp">
          Resetting the token logs out every KOReader device.
        </p>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
import { APP_BASE } from "@/api/v4/base";
import ClipBoard from "@/components/clipboard.vue";

export default {
  name: "KOReaderSync",
  components: {
    ClipBoard,
  },
  props: {
    username: { type: String, default: "" },
  },
  computed: {
    serverURL() {
      // Origin plus url_path_prefix: KOReader appends the kosync paths.
      return `${globalThis.location.origin}${APP_BASE}koreader`;
    },
  },
};
</script>

<style scoped lang="scss">
.koreaderSync {
  margin-top: 0.5em;
}

.koreaderHelp {
  color: rgb(var(--v-theme-text-disabled));
  padding-bottom: 0.5em;
}

.koreaderValue {
  padding-bottom: 0.5em;
}

.koreaderTable td {
  padding: 4px;
}

.helpValue {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
}
</style>
