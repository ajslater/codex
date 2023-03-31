<template>
  <div v-if="stats" id="stats">
    <div class="statBlock">
      <h3>Platform</h3>
      <v-table class="highlight-table">
        <tbody>
          <tr>
            <td>Docker</td>
            <td>{{ stats.platform.docker }}</td>
          </tr>
          <tr>
            <td>Machine</td>
            <td>{{ stats.platform.machine }}</td>
          </tr>
          <tr>
            <td>System</td>
            <td>
              {{ stats.platform.system }} {{ stats.platform.systemRelease }}
            </td>
          </tr>
          <tr>
            <td>Python</td>
            <td>{{ stats.platform.python }}</td>
          </tr>
          <tr>
            <td>Codex</td>
            <td>{{ stats.platform.codex }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>

    <div class="statBlock">
      <h3>Config</h3>
      <v-table class="highlight-table">
        <tbody>
          <tr>
            <td>Libraries</td>
            <td>{{ nf(stats.config.libraryCount) }}</td>
          </tr>
          <tr>
            <td>Anonymous Users</td>
            <td>{{ nf(stats.config.sessionAnonCount) }}</td>
          </tr>
          <tr>
            <td>Registered Users</td>
            <td>{{ nf(stats.config.userCount) }}</td>
          </tr>
          <tr>
            <td>Groups</td>
            <td>{{ nf(stats.config.groupCount) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
    <div class="statBlock">
      <h3>Groups</h3>
      <v-table class="highlight-table">
        <tbody>
          <tr>
            <td>Folders</td>
            <td>{{ nf(stats.groups.folderCount) }}</td>
          </tr>
          <tr>
            <td>Publishers</td>
            <td>{{ nf(stats.groups.publisherCount) }}</td>
          </tr>
          <tr>
            <td>Imprints</td>
            <td>{{ nf(stats.groups.imprintCount) }}</td>
          </tr>
          <tr>
            <td>Series</td>
            <td>{{ nf(stats.groups.seriesCount) }}</td>
          </tr>
          <tr>
            <td>Volumes</td>
            <td>{{ nf(stats.groups.volumeCount) }}</td>
          </tr>
          <tr>
            <td>Issues</td>
            <td>
              {{ nf(stats.groups.comicCount) }}
            </td>
          </tr>
          <tr v-if="stats.fileTypes.cbzCount">
            <td class="indent">CBZ</td>
            <td>{{ nf(stats.fileTypes.cbzCount) }}</td>
          </tr>
          <tr v-if="stats.fileTypes.cbrCount">
            <td class="indent">CBR</td>
            <td>{{ nf(stats.fileTypes.cbrCount) }}</td>
          </tr>
          <tr v-if="stats.fileTypes.cbxCount">
            <td class="indent">CBX</td>
            <td>{{ nf(stats.fileTypes.cbxCount) }}</td>
          </tr>
          <tr v-if="stats.fileTypes.cbtCount">
            <td class="indent">CBT</td>
            <td>{{ nf(stats.fileTypes.cbtCount) }}</td>
          </tr>
          <tr v-if="stats.fileTypes.pdfCount">
            <td class="indent">PDF</td>
            <td>{{ nf(stats.fileTypes.pdfCount) }}</td>
          </tr>
          <tr v-if="stats.fileTypes.unknownCount">
            <td class="indent">Unknown</td>
            <td>{{ nf(stats.fileTypes.unknownCount) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
    <div class="statBlock">
      <h3>Metadata</h3>
      <v-table class="highlight-table">
        <tbody>
          <tr>
            <td>Characters</td>
            <td>{{ nf(stats.metadata.characterCount) }}</td>
          </tr>
          <tr>
            <td>Genres</td>
            <td>{{ nf(stats.metadata.genreCount) }}</td>
          </tr>
          <tr>
            <td>Locations</td>
            <td>{{ nf(stats.metadata.locationCount) }}</td>
          </tr>
          <tr>
            <td>Series Groups</td>
            <td>{{ nf(stats.metadata.seriesGroupCount) }}</td>
          </tr>
          <tr>
            <td>Story Arcs</td>
            <td>{{ nf(stats.metadata.storyArcCount) }}</td>
          </tr>
          <tr>
            <td>Tags</td>
            <td>{{ nf(stats.metadata.tagCount) }}</td>
          </tr>
          <tr>
            <td>Teams</td>
            <td>{{ nf(stats.metadata.teamCount) }}</td>
          </tr>
          <tr>
            <td>Credits</td>
            <td>{{ nf(stats.metadata.creatorCount) }}</td>
          </tr>
          <tr>
            <td class="indent">Roles</td>
            <td>{{ nf(stats.metadata.creatorRoleCount) }}</td>
          </tr>
          <tr>
            <td class="indent">Creators</td>
            <td>{{ nf(stats.metadata.creatorPersonCount) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
    <div class="statBlock">
      <h3>API</h3>
      <v-table class="highlight-table">
        <tbody>
          <tr>
            <td>Schema Documentation:</td>
            <td>
              The only endpoint accessible with API Key access is
              <a
                :href="`${apiSchemaURL}#/api/api_v3_admin_stats_retrieve`"
                target="_blank"
                >/admin/stats</a
              >
            </td>
          </tr>
          <tr id="apiKeyRow" @click="onClickAPIKey">
            <td>
              API Key
              <v-icon class="clipBoardIcon" size="small">{{
                clipBoardIcon
              }}</v-icon>
              <v-fade-transition>
                <span v-show="showTooltip.show" class="copied">Copied</span>
              </v-fade-transition>
            </td>
            <td id="apiKey">{{ stats.config.apiKey }}</td>
          </tr>
          <tr>
            <td colspan="2">
              <ConfirmDialog
                button-text="Regenerate API Key"
                title-text="Regenerate"
                object-name="API Key"
                confirm-text="Regenerate"
                @confirm="regenAPIKey"
              />
            </td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </div>
</template>

<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline } from "@mdi/js";
import { numberFormat } from "humanize";
import { mapActions, mapState } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { copyToClipboard } from "@/copy-to-clipboard";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminTasksTab",
  components: {
    ConfirmDialog,
  },
  data() {
    return {
      showTooltip: { show: false },
      apiSchemaURL: window.CODEX.API_V3_PATH,
    };
  },
  computed: {
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
    clipBoardIcon() {
      return this.showTooltip ? mdiClipboardCheckOutline : mdiClipboardOutline;
    },
  },
  created() {
    this.loadStats();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadStats", "updateAPIKey"]),
    regenAPIKey() {
      this.updateAPIKey().then(this.loadStats).catch(console.warn);
    },
    nf(val) {
      return numberFormat(val, 0);
    },
    onClickAPIKey() {
      copyToClipboard(this.stats.config.apiKey, this.showTooltip);
    },
  },
};
</script>

<style scoped lang="scss">
.statBlock {
  display: inline-block;
  vertical-align: top;
  margin-right: 40px;
}
h3 {
  margin-top: 1em;
  text-align: center;
}
.highlight-table {
  color: rgb(var(--v-theme-textSecondary));
}
tr td:nth-child(2) {
  text-align: right;
}
.indent {
  padding-left: 2em !important;
}
.copied {
  font-size: small;
  font-weight: normal;
  color: rgb(var(--v-theme-textSecondary));
}
.clipBoardIcon {
  color: rgb(var(--v-theme-iconsInactive));
}
#apiKeyRow:hover {
  background-color: rgb(var(--v-theme-surface));
}
#apiKeyRow:hover .clipBoardIcon,
#apiKeyRow:hover #apiKey {
  color: rgb(var(--v-theme-textPrimary));
}
</style>
