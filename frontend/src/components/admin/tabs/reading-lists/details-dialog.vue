<template>
  <v-dialog v-model="show" max-width="560px">
    <v-card>
      <v-card-title class="dialogTitle">Edit Details</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="name"
          label="Name"
          density="compact"
          :rules="[nameRule]"
          autofocus
        />
        <v-textarea
          v-model="description"
          label="Description"
          density="compact"
          rows="3"
          auto-grow
          hint="Kept when the list is refreshed or recombined."
          persistent-hint
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Cancel</v-btn>
        <v-btn
          variant="tonal"
          :disabled="!name.trim() || saving"
          :title="name.trim() ? '' : 'A list needs a name.'"
          @click="save"
        >
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapActions } from "pinia";

import { useReadingListsStore } from "@/stores/reading-lists";

/*
 * Rename a reading list and give it a description. A hand-given name or
 * description stays through refreshes and recombines.
 */
export default {
  name: "ReadingListDetailsDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    readingList: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  data() {
    return { name: "", description: "", saving: false };
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
    modelValue: {
      immediate: true,
      handler(value) {
        if (!value) return;
        this.name = this.readingList.name || "";
        this.description = this.readingList.description || "";
      },
    },
  },
  methods: {
    ...mapActions(useReadingListsStore, ["updateDetails"]),
    nameRule(value) {
      return Boolean((value || "").trim()) || "A list needs a name.";
    },
    async save() {
      this.saving = true;
      try {
        const saved = await this.updateDetails(this.readingList.pk, {
          name: this.name.trim(),
          description: this.description,
        });
        if (saved) this.show = false;
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@layer codex-components {
  .dialogTitle {
    font-weight: bold;
  }
}
</style>
