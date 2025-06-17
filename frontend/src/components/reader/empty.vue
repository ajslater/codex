<template>
  <ReaderTopToolbar />
  <EmptyState
    headline="Book Not Found"
    title="Close the reader and find another book"
    :icon="mdiBookRemoveOutline"
    action-text="Try to load book again"
    @click:action="onAction"
  />
</template>

<script>
import { mdiBookRemoveOutline } from "@mdi/js";
import { mapActions } from "pinia";

import EmptyState from "@/components/empty.vue";
import ReaderTopToolbar from "@/components/reader/toolbars/top/reader-toolbar-top.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderEmptyBooks",
  components: {
    ReaderTopToolbar,
    EmptyState,
  },
  data() {
    return {
      mdiBookRemoveOutline,
    };
  },
  methods: {
    ...mapActions(useReaderStore, ["loadBooks", "setShowToolbars"]),
    onAction() {
      this.loadBooks({ mtime: Date.now() });
    },
  },
  created() {
    this.setShowToolbars();
  },
};
</script>
