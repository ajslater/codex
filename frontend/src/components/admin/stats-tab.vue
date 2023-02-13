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
            <td>{{ stats.config.libraryCount }}</td>
          </tr>
          <tr>
            <td>Anonymous Users</td>
            <td>{{ stats.config.sessionAnonCount }}</td>
          </tr>
          <tr>
            <td>Registered Users</td>
            <td>{{ stats.config.userCount }}</td>
          </tr>
          <tr>
            <td>Groups</td>
            <td>{{ stats.config.groupCount }}</td>
          </tr>
          <tr>
            <td>API Key</td>
            <td>{{ stats.config.apiKey }}</td>
          </tr>
          <tr>
            <td colspan="2">
              <ConfirmDialog
                button-text="Regenerate API Key"
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
            <td>{{ stats.groups.folderCount }}</td>
          </tr>
          <tr>
            <td>Publishers</td>
            <td>{{ stats.groups.publisherCount }}</td>
          </tr>
          <tr>
            <td>Imprints</td>
            <td>{{ stats.groups.imprintCount }}</td>
          </tr>
          <tr>
            <td>Series</td>
            <td>{{ stats.groups.seriesCount }}</td>
          </tr>
          <tr>
            <td>Volumes</td>
            <td>{{ stats.groups.volumeCount }}</td>
          </tr>
          <tr>
            <td>Issues</td>
            <td>
              {{ stats.groups.comicCount }}
            </td>
          </tr>
          <tr>
            <td>Comics</td>
            <td>{{ stats.groups.comicArchiveCount }}</td>
          </tr>
          <tr>
            <td>PDFs</td>
            <td>{{ stats.groups.pdfCount }}</td>
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
            <td>{{ stats.metadata.characterCount }}</td>
          </tr>
          <tr>
            <td>Credits</td>
            <td>{{ stats.metadata.creditCount }}</td>
          </tr>
          <tr>
            <td>Roles</td>
            <td>{{ stats.metadata.creditRoleCount }}</td>
          </tr>
          <tr>
            <td>Creators</td>
            <td>{{ stats.metadata.creditPersonCount }}</td>
          </tr>
          <tr>
            <td>Genres</td>
            <td>{{ stats.metadata.genreCount }}</td>
          </tr>
          <tr>
            <td>Locations</td>
            <td>{{ stats.metadata.locationCount }}</td>
          </tr>
          <tr>
            <td>Series Groups</td>
            <td>{{ stats.metadata.seriesGroupCount }}</td>
          </tr>
          <tr>
            <td>Story Arcs</td>
            <td>{{ stats.metadata.storyArcCount }}</td>
          </tr>
          <tr>
            <td>Tags</td>
            <td>{{ stats.metadata.tagCount }}</td>
          </tr>
          <tr>
            <td>Teams</td>
            <td>{{ stats.metadata.teamCount }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </div>
</template>

<script>
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
    console.log("CREATED");
    this.loadStats();
    console.log(this.stats);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadStats", "updateAPIKey"]),
    regenAPIKey() {
      this.updateAPIKey().then(this.loadStats).catch(console.warn);
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
