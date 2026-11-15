<template>
  <div class="shelfNameInput">
    <v-combobox
      v-model="name"
      class="shelfNameCombobox"
      :autofocus="autofocus"
      density="compact"
      :error-messages="shownError"
      hide-details="auto"
      :items="suggestions"
      label="Shelf Name"
      :maxlength="maxLength"
      :menu-props="{ maxHeight: 200 }"
      variant="outlined"
      @keydown.enter="onEnter"
      @keydown.esc.stop="$emit('cancel')"
      @update:model-value="serverError = ''"
    />
    <v-btn
      class="shelfNameSubmit"
      density="compact"
      :disabled="!isValid"
      :icon="mdiCheck"
      size="small"
      title="Create Shelf"
      variant="text"
      @click="submit"
    />
    <v-btn
      class="shelfNameCancel"
      density="compact"
      :icon="mdiClose"
      size="small"
      title="Cancel"
      variant="text"
      @click="$emit('cancel')"
    />
  </div>
</template>

<script>
import { mdiCheck, mdiClose } from "@mdi/js";

/*
 * Starter names offered for a new shelf. All shelves are equal: these
 * are only suggestions, none of them is special once created.
 */
export const SHELF_NAME_SUGGESTIONS = Object.freeze([
  "Want to Read",
  "Favorites",
  "Reading Now",
  "Finished",
]);
// The server's limit on a shelf name.
export const SHELF_NAME_MAX_LENGTH = 128;

export default {
  name: "ShelfNameInput",
  props: {
    autofocus: {
      type: Boolean,
      default: true,
    },
    // Names already taken: never suggested, and rejected as duplicates.
    existingNames: {
      type: Array,
      default: () => [],
    },
    // Set by the parent when the server refuses the submitted name.
    error: {
      type: String,
      default: "",
    },
  },
  emits: ["cancel", "submit"],
  data() {
    return {
      maxLength: SHELF_NAME_MAX_LENGTH,
      mdiCheck,
      mdiClose,
      name: "",
      serverError: "",
    };
  },
  computed: {
    suggestions() {
      return SHELF_NAME_SUGGESTIONS.filter(
        (name) => !this.existingNames.includes(name),
      );
    },
    trimmedName() {
      return (this.name ?? "").toString().trim();
    },
    isDuplicate() {
      return this.existingNames.includes(this.trimmedName);
    },
    isValid() {
      return (
        this.trimmedName.length > 0 &&
        this.trimmedName.length <= SHELF_NAME_MAX_LENGTH &&
        !this.isDuplicate
      );
    },
    shownError() {
      if (this.isDuplicate) return "A shelf with this name already exists";
      return this.serverError;
    },
  },
  watch: {
    error: {
      immediate: true,
      handler(to) {
        this.serverError = to;
      },
    },
  },
  methods: {
    onEnter() {
      /*
       * Enter on a highlighted suggestion also picks it; wait a tick so
       * the pick lands in ``name`` before it is submitted.
       */
      this.$nextTick(this.submit);
    },
    submit() {
      if (!this.isValid) return;
      this.$emit("submit", this.trimmedName);
    },
  },
};
</script>

<style scoped lang="scss">
.shelfNameInput {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.shelfNameCombobox {
  flex: 1;
  min-width: 12em;
}

.shelfNameSubmit,
.shelfNameCancel {
  flex-shrink: 0;
  margin-top: 8px;
}
</style>
