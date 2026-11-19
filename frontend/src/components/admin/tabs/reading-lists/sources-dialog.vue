<template>
  <v-dialog v-model="show" max-width="760px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">
        Sources of {{ readingList.name }}
      </v-card-title>
      <v-card-text>
        <p class="adminProse">
          The list is its sources combined. The first source's order wins; the
          others add their issues beside their neighbours and every id they
          know. Removing a source recomputes the list without it.
        </p>
        <div
          v-for="(source, index) in sources"
          :key="source.pk"
          class="adminCard sourceRow"
        >
          <div class="adminCardInfo">
            <div class="adminCardTitle">
              {{ index === 0 ? "Primary · " : "" }}{{ label(source) }}
            </div>
            <div class="adminCardDesc">
              <span v-if="source.attribution">
                {{ source.attribution.toUpperCase() }} ·
              </span>
              <span class="ref">{{ source.ref }}</span>
              <span v-if="!source.ordered"> · unordered</span>
            </div>
          </div>
          <span class="adminActionCell">
            <v-btn
              :icon="mdiArrowUp"
              size="small"
              density="compact"
              variant="text"
              :disabled="index === 0"
              title="Rank higher"
              @click="rank(index, -1)"
            />
            <v-btn
              :icon="mdiArrowDown"
              size="small"
              density="compact"
              variant="text"
              :disabled="index === sources.length - 1"
              title="Rank lower"
              @click="rank(index, 1)"
            />
            <v-btn
              :icon="mdiRefresh"
              size="small"
              density="compact"
              variant="text"
              :disabled="!source.refreshable"
              :title="
                source.refreshable
                  ? 'Fetch again'
                  : 'Uploads and tags have nothing to fetch.'
              "
              @click="refresh(source)"
            />
            <ConfirmDialog
              :icon="mdiTrashCanOutline"
              size="small"
              density="compact"
              variant="text"
              confirm-text="Remove"
              title-text="Remove source"
              :text="removeText(source)"
              @confirm="remove(source)"
            />
          </span>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-btn variant="tonal" size="small" @click="addSource">
          Add Source
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import {
  mdiArrowDown,
  mdiArrowUp,
  mdiRefresh,
  mdiTrashCanOutline,
} from "@mdi/js";

import { mapState } from "pinia";

import * as API from "@/api/v4/reading-lists";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useCommonStore } from "@/stores/common";
import { SOURCE_KINDS, useReadingListsStore } from "@/stores/reading-lists";

export default {
  name: "SourcesDialog",
  components: { ConfirmDialog },
  props: {
    modelValue: { type: Boolean, default: false },
    readingList: { type: Object, required: true },
  },
  emits: ["update:modelValue", "changed", "add-source"],
  data() {
    return {
      mdiArrowDown,
      mdiArrowUp,
      mdiRefresh,
      mdiTrashCanOutline,
    };
  },
  computed: {
    ...mapState(useReadingListsStore, ["listsByPk"]),
    sources() {
      // The table's live row, so a source added or removed shows at once.
      const row = this.listsByPk[this.readingList.pk] || this.readingList;
      return row.sources || [];
    },
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
  },
  methods: {
    label(source) {
      return SOURCE_KINDS[source.kind] || source.kind;
    },
    removeText(source) {
      return `Remove ${this.label(source)} from ${this.readingList.name}? Its issues leave the list unless another source has them. A list left with nothing is deleted.`;
    },
    async call(promise, message) {
      try {
        await promise;
        if (message) useCommonStore().setNotice(message);
        this.$emit("changed");
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      }
    },
    async rank(index, step) {
      const order = [...this.sources];
      const [moved] = order.splice(index, 1);
      order.splice(index + step, 0, moved);
      await this.call(
        API.rankSources(
          this.readingList.pk,
          order.map((source) => source.pk),
        ),
      );
    },
    async refresh(source) {
      await this.call(
        API.refreshSource(this.readingList.pk, source.pk),
        `Fetching ${this.label(source)} again. The list changes if it did.`,
      );
    },
    async remove(source) {
      const last = this.sources.length <= 1;
      await this.call(
        API.removeSource(this.readingList.pk, source.pk),
        last
          ? "Removed its last source: the list is deleted."
          : `Removed ${this.label(source)}; the list is recomputed without it.`,
      );
      if (last) this.show = false;
    },
    addSource() {
      // Stays open: the new source shows here once it is imported.
      this.$emit("add-source", this.readingList);
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .sourceRow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: $space-2;
  }

  .ref {
    word-break: break-all;
  }

  .dialogTitle {
    font-weight: bold;
  }
}
</style>
