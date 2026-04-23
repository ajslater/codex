<template>
  <v-btn
    aria-label="tags"
    class="tagButton cardControlButton"
    :variant="variant"
    :icon="mdiTagOutline"
    title="Tags"
    @mouseenter="lazyImportEnabled ? onMouseEnter : null"
    @click.prevent
  />
</template>
<script>
import { mdiTagOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "../../stores/auth";
import { useMetadataStore } from "../../stores/metadata";

export default {
  name: "MetadataActivator",
  props: {
    book: { type: Object, required: true },
    toolbar: { type: Boolean, require: true },
  },
  data() {
    return {
      mdiTagOutline,
      lazyImportStarted: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      stateLazyImportEnabled: (state) => state.adminFlags?.lazyImportMetadata,
    }),
    lazyImportEnabled() {
      return (
        this.stateLazyImportMetadata &&
        this.book &&
        this.book.group === "c" &&
        !this.book.hasMetadata &&
        !this.lazyImportStarted
      );
    },
    variant() {
      return this.toolbar ? "plain" : "text";
    },
  },
  methods: {
    ...mapActions(useMetadataStore, ["lazyImport"]),
    onMouseEnter() {
      if (this.lazyImportEnabled) {
        const ids = this.book.ids || [this.book.pk];
        this.lazyImport({ group: this.book.group, ids }).then(() => {
          this.lazyImportStarted = true;
        });
      }
    },
  },
};
</script>
