<template>
  <div v-if="failedImports && failedImports.length > 0" id="failedImports">
    <h4>Failed Imports</h4>
    <v-simple-table class="highlight-simple-table" fixed-header>
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
    </v-simple-table>
    <v-expansion-panels>
      <v-expansion-panel id="failedImportsHelp">
        <v-expansion-panel-header
          ><h5>Failed Imports Help</h5></v-expansion-panel-header
        >
        <v-expansion-panel-content>
          <p>
            These are Comic archives that have failed to import. This list is
            updated every time the library updates. You should probably review
            these files and fix or remove them.
          </p>

          <h4>Fixing comics</h4>
          <p>
            Try using the zip fixer to fix comics:
            <code class="cli">
              cp problem-comic.cbz /somewhere/safe/problem-comic.cbz.backup<br />
              zip -F problem-comic.cbz --out fixed.zip<br />
              mv fixed.zip problem-comic.cbz
            </code>

            I've found that even if the fixed comic looks exactly the same as
            the original, replacing the original with the fixed archive can
            often get Codex to import it properly. If you've removed or fixed
            the unimportable comics in your library you can try polling the
            library again. You may also try zip -FF to fix comics which uses a
            different (not necissarily better) algorithm. If you fix some
            imports, and Codex does not immediately detect the change, poll the
            library the fixed comics are in.
          </p>

          <h4>Reporting Issues</h4>
          <p>
            If the comic looks good to you, but still shows up as a failed
            import, it might be Codex's fault for not importing it correctly.
            Please file an
            <a href="https://github.com/ajslater/codex/issues/" target="_blank"
              >Issue Report<v-icon small>{{ mdiOpenInNew }}</v-icon></a
            >
            and include the stack trace from the logs at
            <code>config/logs/codex.log</code>
            if you can.
          </p>
        </v-expansion-panel-content>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapState } from "pinia";

import DateTimeColumn from "@/components/admin/datetime-column.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminFailedImportsPanel",
  components: {
    DateTimeColumn,
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      failedImports: (state) => state.failedImports,
    }),
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
#failedImportsHelp {
  color: lightgrey;
}
@import "../anchors.scss";
</style>
