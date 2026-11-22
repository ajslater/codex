<template>
  <div class="listNameInput">
    <v-combobox
      v-model="name"
      class="listNameCombobox"
      :autofocus="autofocus"
      density="compact"
      :error-messages="shownError"
      hide-details="auto"
      :items="suggestions"
      label="Reading List Name"
      :maxlength="maxLength"
      :menu-props="{ maxHeight: 200 }"
      variant="outlined"
      @keydown.enter="onEnter"
      @keydown.esc.stop="$emit('cancel')"
      @update:model-value="serverError = ''"
    />
    <v-btn
      class="listNameSubmit"
      density="compact"
      :disabled="!isValid"
      :icon="mdiCheck"
      size="small"
      :title="submitTitle"
      variant="text"
      @click="submit"
    />
    <v-btn
      class="listNameCancel"
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

import LIMITS from "@/choices/limits.json";
import { isImeEnter } from "@/util";

/*
 * Starter names offered for a new list. All lists are equal: these are
 * only suggestions, none of them is special once created.
 */
export const LIST_NAME_SUGGESTIONS = Object.freeze([
  "Want to Read",
  "Favorites",
  "Reading Now",
]);
// The server's limit on a list name.
export const LIST_NAME_MAX_LENGTH = LIMITS.maxNameLen;

export default {
  name: "ListNameInput",
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
    // What the check button does: make the list, with what for.
    submitTitle: {
      type: String,
      default: "Create Reading List",
    },
  },
  emits: ["cancel", "submit"],
  data() {
    return {
      maxLength: LIST_NAME_MAX_LENGTH,
      mdiCheck,
      mdiClose,
      name: "",
      serverError: "",
    };
  },
  computed: {
    suggestions() {
      return LIST_NAME_SUGGESTIONS.filter(
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
        this.trimmedName.length <= LIST_NAME_MAX_LENGTH &&
        !this.isDuplicate
      );
    },
    shownError() {
      if (this.isDuplicate) {
        return "You already have a reading list with that name.";
      }
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
    onEnter(event) {
      if (isImeEnter(event)) return;
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
.listNameInput {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.listNameCombobox {
  flex: 1;
  min-width: 12em;
}

.listNameSubmit,
.listNameCancel {
  flex-shrink: 0;
  margin-top: 8px;
}
</style>
