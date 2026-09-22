<!--
  Bottom-of-Libraries-tab panel listing comics and folders that vanished
  from disk but are being kept for their read progress. The conceptual
  sibling of Failed Imports -- "on disk, could not import" next to "not
  on disk, not deleted yet" -- and copied from its presentation.

  The only window onto this state. The visibility filter hides a stamped
  row from every browsing surface with no staff exemption, so without
  this panel an admin could not tell what is being held, could not put
  one back, and could not force an early delete.
-->
<template>
  <div v-if="showPendingDeletes" id="pendingDeletes" class="pendingDeletes">
    <AdminSection title="Pending Deletes">
      <template #actions>
        <div class="pendingDeletesActions">
          <v-btn variant="text" size="small" @click="reapNow">
            Delete Expired Now
          </v-btn>
          <span class="pendingCount">
            <v-icon :icon="mdiClockAlert" size="small" class="pendingIcon" />
            {{ pendingDeletes.length }}
          </span>
        </div>
      </template>
      <template #hint>
        {{ hint }}
      </template>
      <v-table id="pendingDeletesTable" striped="odd">
        <template #default>
          <thead>
            <tr>
              <th>Path</th>
              <th>Type</th>
              <th>Missing Since</th>
              <th>Deleted After</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in pendingDeletes"
              :key="`pd:${item.collection}:${item.pk}`"
            >
              <td class="pathCol">
                {{ item.path }}
              </td>
              <td class="typeCol">
                {{ typeLabel(item.collection) }}
              </td>
              <td class="dateCol">
                <DateTimeColumn :dttm="item.missingSince" />
              </td>
              <td class="dateCol">
                <DateTimeColumn :dttm="item.reapAfter" />
              </td>
              <td class="actionCol">
                <v-btn
                  variant="text"
                  size="small"
                  @click="revive(item.collection, item.pk)"
                >
                  Keep
                </v-btn>
              </td>
            </tr>
          </tbody>
        </template>
      </v-table>
    </AdminSection>
  </div>
</template>

<script>
import { mdiClockAlert } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import { useAdminStore } from "@/stores/admin";

const TYPE_LABELS = Object.freeze({ comics: "Comic", folders: "Folder" });

export default {
  name: "AdminPendingDeletesPanel",
  components: {
    AdminSection,
    DateTimeColumn,
  },
  data() {
    return {
      mdiClockAlert,
      hint: `These comics and folders disappeared from a library. Codex keeps
        them for a day in case they come back, so a filesystem outage does not
        lose your read progress. They are hidden from the browser until then,
        for you too -- this list is the only place they appear. Keep one to
        stop its countdown; a comic whose file returns is restored on its own
        by the next scan. See also Failed Imports below.`,
    };
  },
  computed: {
    ...mapState(useAdminStore, ["pendingDeletes"]),
    showPendingDeletes() {
      return Boolean(this.pendingDeletes?.length);
    },
  },
  watch: {
    // Re-scroll if the deep link fires while already on the Libraries tab.
    "$route.hash"() {
      this.maybeScroll();
    },
    // The panel mounts only once something goes missing; scroll once it
    // appears.
    showPendingDeletes(isShown) {
      if (isShown) this.maybeScroll();
    },
  },
  mounted() {
    this.maybeScroll();
  },
  methods: {
    ...mapActions(useAdminStore, ["revivePendingDelete", "librarianTask"]),
    maybeScroll() {
      if (this.$route.hash !== "#pendingDeletes") return;
      this.$nextTick(() => {
        const el = document.getElementById("pendingDeletes");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
    typeLabel(collection) {
      return TYPE_LABELS[collection] ?? collection;
    },
    revive(collection, pk) {
      this.revivePendingDelete(collection, pk);
    },
    reapNow() {
      // The nightly job, run on demand through the ordinary task
      // endpoint -- which also gets the Jobs-tab progress row for free.
      this.librarianTask("reap_pending_deletes");
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/design.scss" as d;
@use "@/components/anchors.scss";

.pendingDeletes {
  margin-top: d.$space-4;
}

.pendingDeletesActions {
  display: flex;
  align-items: center;
  gap: d.$space-2;
}

.pendingCount {
  color: rgb(var(--v-theme-warning));
}

.pendingIcon {
  color: rgb(var(--v-theme-warning));
}

#pendingDeletesTable {
  background-color: inherit;
}

.pathCol {
  word-break: break-all;
}

.typeCol {
  color: rgb(var(--v-theme-text-secondary));
}

.actionCol {
  text-align: right;
  white-space: nowrap;
}
</style>
