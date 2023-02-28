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
          <tr>
            <td>API Key</td>
            <td>{{ stats.config.apiKey }}</td>
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
          <tr>
            <td>Comics</td>
            <td>{{ nf(stats.groups.comicArchiveCount) }}</td>
          </tr>
          <tr>
            <td>PDFs</td>
            <td>{{ nf(stats.groups.pdfCount) }}</td>
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
            <td>Credits</td>
            <td>{{ nf(stats.metadata.creditCount) }}</td>
          </tr>
          <tr>
            <td>Roles</td>
            <td>{{ nf(stats.metadata.creditRoleCount) }}</td>
          </tr>
          <tr>
            <td>Creators</td>
            <td>{{ nf(stats.metadata.creditPersonCount) }}</td>
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
        </tbody>
      </v-table>
    </div>
  </div>
</template>

<script>
import { numberFormat } from "humanize";
import { mapActions, mapState } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminTasksTab",
  components: {
    ConfirmDialog,
  },
  computed: {
    ...mapState(useCommonStore, {}),
    ...mapState(useAdminStore, {
      stats: (state) => state.stats,
    }),
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
</style>
