<template>
  <button class="missingRunCard" type="button" @click="$emit('expand', runKey)">
    <span class="missingRunCount">{{ count }} more missing</span>
    <span class="missingRunHint text-caption">Show them</span>
  </button>
</template>

<script>
/*
 * A long run of missing issues, folded into one card that opens it.
 */
export default {
  name: "MissingRunCard",
  props: {
    count: { type: Number, required: true },
    runKey: { type: Number, required: true },
  },
  emits: ["expand"],
};
</script>

<style scoped lang="scss">
@use "@/components/book-cover" as bookcover;

@layer codex-components {
  .missingRunCard {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: bookcover.$cover-height;
    width: bookcover.$cover-width;
    border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 4px;
    color: rgb(var(--v-theme-text-secondary));
    background: transparent;
    cursor: pointer;
  }

  .missingRunCard:hover,
  .missingRunCard:focus-visible {
    color: rgb(var(--v-theme-primary));
    border-color: rgb(var(--v-theme-primary));
  }

  .missingRunCount {
    font-size: 16px;
  }
}
</style>
