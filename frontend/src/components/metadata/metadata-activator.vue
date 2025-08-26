<template>
  <v-btn
    @mouseenter="onMouseEnter"
    aria-label="tags"
    class="tagButton cardControlButton"
    :variant="variant"
    :icon="mdiTagOutline"
    title="Tags"
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
    return { mdiTagOutline };
  },
  computed: {
    ...mapState(useAuthStore, {
      lazyImportEnabled: (state) => state.adminFlags.lazyImportMetadata,
    }),
    variant() {
      return this.toolbar ? "plain" : "text";
    },
  },
  methods: {
    ...mapActions(useMetadataStore, ["lazyImport"]),
    onMouseEnter() {
      if (
        this.lazyImportEnabled &&
        this.book.group === "c" &&
        !this.book.hasMetadata
      ) {
        const ids = this.book.ids || [this.book.pk];
        this.lazyImport({ group: this.book.group, ids });
        this.book.hasMetadata = true;
      }
    },
  },
};
</script>
