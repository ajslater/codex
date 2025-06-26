<template>
  <v-expansion-panels>
    <v-expansion-panel>
      <v-expansion-panel-title>
        <h4 id="coverDirHeader">Custom Covers</h4>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <AdminLibraryTable
          :items="customCoverLibraries"
          disable-sort
          :covers-dir="true"
        />
        <v-expansion-panels>
          <v-expansion-panel id="customCoversHelp">
            <v-expansion-panel-title>
              <h4>Custom Covers Help</h4>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <p>Custom covers may be added to the browser in two locations:</p>
              <h4>Folders</h4>
              <p>
                A library folder with a file named
                <code>.codex-cover.jpg</code> will show a custom cover for that
                folder in Folder view. The addition and removal of these covers
                by watching filesystem events and polling is handled by the
                library that folder belongs to.
              </p>
              <h4>Custom Covers Dir</h4>
              <p>
                The Codex config directory has a special folder named
                <code>custom-covers</code> under which are subdirectories for
                each of the browser groups that may adopt custom covers. Images
                in these subdirectories that match the name of the browser group
                will be used as custom covers. For instance:
                <code
                  >.../custom-covers/publishers/American Comics Group.webp</code
                >
                would be used as the cover for the publisher "American Comics
                Group". <code>.../custom-covers/series/arrow.png</code> would be
                used as the cover for every series named "Arrow", for
                <em>every</em> publisher. Similar to a comic library, the
                <code>custom-covers</code> directory may be watched and polled
                for changes. By default it is neither watched nor polled and
                must be enabled by the admin.
              </p>
              <h4>Image Formats & Size</h4>
              <p>
                Custom covers are detected only for files with the extensions:
                <code>.bmp, .gif, .jpeg, .jpg, .png, .webp</code>.
              </p>
              <p>
                Browser covers are transformed from their sources to 165px x
                254px thumbnails. Custom covers will transform most
                aesthetically the closer to that ratio they are.
              </p>
              <h4>Priority</h4>
              <p>
                Custom covers supersede covers set by the user's individual
                browser settings.
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>
<script>
import { mapState } from "pinia";

import AdminLibraryTable from "@/components/admin/tabs/library-table.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminCustomCoversPanel",
  components: {
    AdminLibraryTable,
  },
  computed: {
    ...mapState(useAdminStore, ["customCoverLibraries"]),
  },
};
</script>
<style scoped lang="scss">
#customCoversHelp {
  color: rgb(var(--v-theme-textSecondary));
}

#customCoversHelp :deep(.v-expansion-panel-text h4) {
  margin-top: 0.5em;
}
</style>
