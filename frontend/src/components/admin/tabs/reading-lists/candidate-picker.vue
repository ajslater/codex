<template>
  <v-dialog v-model="show" max-width="640px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">
        {{ mapSeries ? "Map series" : "Find the comic" }}:
        {{ entry.seriesName }} #{{ entry.issue }}
        <span v-if="entry.year">({{ entry.year }})</span>
      </v-card-title>
      <v-card-text>
        <p v-if="mapSeries" class="adminProse">
          Pick a comic of the library series this list's
          <strong>{{ entry.seriesName }}</strong> is. Every row of it, in this
          list and every other, then matches within that series.
        </p>
        <v-text-field
          v-model="query"
          label="Series name"
          :placeholder="entry.seriesName"
          density="compact"
          hide-details
          clearable
          @keyup.enter="load"
        />
        <v-list density="compact" class="candidates">
          <v-list-item
            v-for="comic in candidates"
            :key="comic.pk"
            :title="comicLabel(comic)"
            :subtitle="comic.name"
            @click="pick(comic)"
          />
          <v-list-item v-if="loaded && !candidates.length">
            No comics found. Search by another series name.
          </v-list-item>
        </v-list>
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="!mapSeries && entry.comic" variant="text" @click="clear">
          Mark Missing
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Cancel</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import * as API from "@/api/v4/reading-lists";
import { useCommonStore } from "@/stores/common";

export default {
  name: "CandidatePicker",
  props: {
    modelValue: { type: Boolean, default: false },
    readingListPk: { type: Number, required: true },
    entry: { type: Object, required: true },
    // Save the picked comic's series as this entry's series, for every row.
    mapSeries: { type: Boolean, default: false },
  },
  emits: ["update:modelValue", "picked"],
  data() {
    return { query: "", candidates: [], loaded: false };
  },
  computed: {
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
  },
  watch: {
    modelValue(value) {
      if (value) {
        this.query = "";
        this.load();
      }
    },
  },
  mounted() {
    if (this.modelValue) this.load();
  },
  methods: {
    comicLabel(comic) {
      const volume = comic.volumeName ? ` ${comic.volumeName}` : "";
      // A year-like volume already says the year.
      const year =
        comic.year && comic.volumeName !== `(${comic.year})`
          ? ` (${comic.year})`
          : "";
      return `${comic.seriesName}${volume} #${comic.issue}${year}`;
    },
    async load() {
      try {
        const response = await API.getCandidates(
          this.readingListPk,
          this.entry.pk,
          this.query || "",
        );
        this.candidates = response.data.candidates || [];
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.loaded = true;
      }
    },
    async pick(comic) {
      try {
        await (this.mapSeries
          ? API.createMapping(this.readingListPk, this.entry.pk, comic.seriesPk)
          : API.updateEntry(this.readingListPk, this.entry.pk, {
              comic: comic.pk,
            }));
        this.$emit("picked");
      } catch (error) {
        useCommonStore().setErrors(error);
      }
    },
    async clear() {
      try {
        await API.updateEntry(this.readingListPk, this.entry.pk, {
          comic: null,
        });
        this.$emit("picked");
      } catch (error) {
        useCommonStore().setErrors(error);
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

@layer codex-components {
  .candidates {
    max-height: 50vh;
    overflow-y: auto;
  }

  .dialogTitle {
    font-weight: bold;
  }
}
</style>
