<!--
  Bottom-of-Libraries-tab panel listing comic archives that failed to import.
  Mirrors the Tag Write Errors panel's AdminSection presentation. The
  ``#failedImports`` anchor is the deep-link target from the sidebar drawer.
-->
<template>
  <div v-if="showFailedImports" id="failedImports" class="failedImports">
    <AdminSection title="Failed Imports">
      <template #actions>
        <div v-if="!failedImportsDismissed" class="failedImportsActions">
          <v-btn variant="text" size="small" @click="dismissFailedImports">
            Clear Warning
          </v-btn>
          <span class="errorCount">
            <v-icon :icon="mdiAlertCircle" size="small" class="errorIcon" />
            {{ failedImports.length }}
          </span>
        </div>
      </template>
      <template #hint>
        These comic archives failed to import. The list refreshes every time the
        library updates — review these files and fix or remove them.
      </template>
      <v-table id="failedImportsTable" striped="odd">
        <template #default>
          <thead>
            <tr>
              <th>Path</th>
              <th>Created</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in failedImports" :key="`fi:${item.path}`">
              <td class="pathCol">
                {{ item.path }}
              </td>
              <td class="dateCol">
                <DateTimeColumn :dttm="item.createdAt" />
              </td>
              <td class="reasonCol">
                {{ item.reason }}
              </td>
            </tr>
          </tbody>
        </template>
      </v-table>
      <v-expansion-panels>
        <v-expansion-panel id="failedImportsHelp">
          <v-expansion-panel-title class="text-title-small">
            Failed Imports Help
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <h4>Fixing comics</h4>
            <p>
              Try using the zip fixer to fix comics:
              <code class="cli">
                cp problem-comic.cbz /somewhere/safe/problem-comic.cbz.backup<br />
                zip -F problem-comic.cbz --out fixed.zip<br />
                mv fixed.zip problem-comic.cbz
              </code>
              You may also try <code>zip -FF</code> to fix comics which uses a
              different (not necissarily better) algorithm. If you fix some
              imports, and Codex does not immediately detect the change, poll
              the library which contains the fixed comics.
            </p>
            <h4>Reporting Issues</h4>
            <p>
              If the comic looks good to you, but still shows up as a failed
              import, it might be Codex's fault for not importing it correctly.
              Please file an
              <a
                href="https://github.com/ajslater/codex/issues/"
                target="_blank"
                >Issue Report<v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
              >
              and include the stack trace from the logs at
              <code>config/logs/codex.log</code>
              if you can.
            </p>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </AdminSection>
  </div>
</template>

<script>
import { mdiAlertCircle, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminFailedImportsPanel",
  components: {
    AdminSection,
    DateTimeColumn,
  },
  data() {
    return {
      mdiAlertCircle,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      failedImports: (state) => state.failedImports,
      failedImportsDismissed: (state) => state.failedImportsDismissed,
      showFailedImports: (state) =>
        state.failedImports && state.failedImports.length > 0,
    }),
  },
  watch: {
    // Re-scroll if the deep link fires while already on the Libraries tab.
    "$route.hash"() {
      this.maybeScroll();
    },
    // The panel mounts only once imports fail; scroll once it appears.
    showFailedImports(isShown) {
      if (isShown) this.maybeScroll();
    },
  },
  mounted() {
    this.maybeScroll();
  },
  methods: {
    ...mapActions(useAdminStore, ["dismissFailedImports"]),
    maybeScroll() {
      if (this.$route.hash !== "#failedImports") return;
      this.$nextTick(() => {
        const el = document.getElementById("failedImports");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/design.scss" as d;
@use "@/components/anchors.scss";

.failedImports {
  margin-top: d.$space-4;
}

// Cluster the Clear Warning button + count together at the right (the header
// is space-between), button immediately left of the icon/number.
.failedImportsActions {
  display: flex;
  align-items: center;
  gap: d.$space-2;
}

.errorCount {
  color: rgb(var(--v-theme-error));
}

.errorIcon {
  color: rgb(var(--v-theme-error));
}

#failedImportsTable {
  background-color: inherit;
}

.pathCol {
  word-break: break-all;
}

.reasonCol {
  color: rgb(var(--v-theme-textSecondary));
}

#failedImportsHelp {
  color: rgb(var(--v-theme-textSecondary));
}

.cli {
  display: block;
  margin-left: 2em;
}

h4 {
  padding-top: 0.5em;
}
</style>
