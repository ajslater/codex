<template>
  <div v-if="failedImports && failedImports.length > 0" id="failedImports">
    <v-expansion-panels>
      <v-expansion-panel
        id="failedImportsPanel"
        @click="unseenFailedImports = false"
      >
        <v-expansion-panel-title>
          <h4>Failed Imports: {{ failedImports.length }}</h4>
          <v-icon
            v-if="unseenFailedImports"
            id="failedImportsIcon"
            title="New Failed Imports"
          >
            {{ mdiBookAlert }}
          </v-icon>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-table class="highlight-table">
            <template #default>
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in failedImports" :key="`fi:${item.path}`">
                  <td>
                    {{ item.path }}
                  </td>
                  <td class="dateCol">
                    <DateTimeColumn :dttm="item.createdAt" />
                  </td>
                </tr>
              </tbody>
            </template>
          </v-table>
          <v-expansion-panels>
            <v-expansion-panel id="failedImportsHelp">
              <v-expansion-panel-title>
                <h4>Failed Imports Help</h4>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <p>
                  These are Comic archives that have failed to import. This list
                  is updated every time the library updates. You should probably
                  review these files and fix or remove them.
                </p>

                <h4>Fixing comics</h4>
                <p>
                  Try using the zip fixer to fix comics:
                  <code class="cli">
                    cp problem-comic.cbz
                    /somewhere/safe/problem-comic.cbz.backup<br />
                    zip -F problem-comic.cbz --out fixed.zip<br />
                    mv fixed.zip problem-comic.cbz
                  </code>
                  You may also try <code>zip -FF</code> to fix comics which uses
                  a different (not necissarily better) algorithm. If you fix
                  some imports, and Codex does not immediately detect the
                  change, poll the library which contains the fixed comics.
                </p>
                <h4>Reporting Issues</h4>
                <p>
                  If the comic looks good to you, but still shows up as a failed
                  import, it might be Codex's fault for not importing it
                  correctly. Please file an
                  <a
                    href="https://github.com/ajslater/codex/issues/"
                    target="_blank"
                    >Issue Report<v-icon size="small">{{
                      mdiOpenInNew
                    }}</v-icon></a
                  >
                  and include the stack trace from the logs at
                  <code>config/logs/codex.log</code>
                  if you can.
                </p>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script>
import { mdiBookAlert, mdiOpenInNew } from "@mdi/js";
import { mapState, mapWritableState } from "pinia";

import DateTimeColumn from "@/components/admin/datetime-column.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminFailedImportsPanel",
  components: {
    DateTimeColumn,
  },
  data() {
    return {
      mdiBookAlert,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAdminStore, ["failedImports"]),
    ...mapWritableState(useAdminStore, ["unseenFailedImports"]),
  },
  created() {
    this.unseenFailedImports = true;
  },
};
</script>

<style scoped lang="scss">
.cli {
  display: block;
  margin-left: 2em;
}
#failedImports {
  margin-top: 60px;
}
#failedImportsIcon {
  padding-left: 0.25em;
  color: rgb(var(--v-theme-error)) !important;
}
#failedImportsHelp {
  color: rgb(var(--v-theme-textSecondary));
}
h4 {
  padding-top: 0.5em;
}
@import "../anchors.scss";
</style>
