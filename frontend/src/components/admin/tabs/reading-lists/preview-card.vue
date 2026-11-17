<template>
  <div class="adminCard previewCard">
    <div class="adminCardHeader">
      <div class="adminCardInfo">
        <div class="adminCardTitle">{{ card.name }}</div>
        <div class="adminCardDesc">
          <span v-if="card.curator">{{ card.curator.toUpperCase() }} · </span>
          <span v-if="card.listType">{{ card.listType }} · </span>
          <span v-if="card.count != null">{{ card.count }} issues</span>
        </div>
      </div>
    </div>
    <div v-if="card.error" class="previewError">{{ card.error }}</div>
    <template v-else>
      <div v-if="card.deferred" class="adminCardDesc">
        Its issues are fetched after Import; coverage appears when the fetch
        finishes.
      </div>
      <div v-else class="coverage">
        <v-progress-linear
          :model-value="card.count ? (100 * card.matched) / card.count : 0"
          height="6"
          rounded
        />
        {{ card.matched }} of {{ card.count }} in your library
      </div>
      <ul v-if="card.warnings?.length" class="warnings">
        <li v-for="(warning, index) in card.warnings" :key="index">
          {{ warning }}
        </li>
      </ul>
      <v-radio-group
        v-if="!into && card.suggestions?.length"
        :model-value="choice.into"
        density="compact"
        hide-details
        @update:model-value="update({ into: $event })"
      >
        <v-radio
          v-for="suggestion in card.suggestions"
          :key="suggestion.pk"
          :value="suggestion.pk"
          :label="suggestionLabel(suggestion)"
        />
        <v-radio :value="null" label="Keep it a list of its own" />
      </v-radio-group>
      <div v-if="!into && !choice.into" class="previewOptions">
        <v-select
          :model-value="choice.private"
          :items="VISIBILITY"
          label="Visibility"
          density="compact"
          hide-details
          class="visibility"
          @update:model-value="update({ private: $event })"
        />
        <v-text-field
          :model-value="choice.name"
          :placeholder="card.name"
          label="Name"
          density="compact"
          hide-details
          @update:model-value="update({ name: $event })"
        />
      </div>
    </template>
  </div>
</template>

<script>
const VISIBILITY = Object.freeze([
  { value: false, title: "Global" },
  { value: true, title: "Private to me" },
]);
const VERDICTS = Object.freeze({
  same: "Same reading order as",
  subset: "Holds the issues of",
  variant: "Another order of",
});

export default {
  name: "PreviewCard",
  props: {
    card: { type: Object, required: true },
    into: { type: Object, default: null },
    modelValue: { type: Object, default: () => ({}) },
  },
  emits: ["update:modelValue"],
  data() {
    return { VISIBILITY };
  },
  computed: {
    choice() {
      return this.modelValue || {};
    },
  },
  methods: {
    update(changes) {
      this.$emit("update:modelValue", { ...this.choice, ...changes });
    },
    suggestionLabel(suggestion) {
      const verdict = VERDICTS[suggestion.verdict] || "Like";
      const action = suggestion.combine ? "Combine with it" : "Combine anyway";
      return `${verdict} ${suggestion.name}: ${action}`;
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .previewCard {
    margin-bottom: $space-3;
  }

  .previewError {
    color: rgb(var(--v-theme-error));
    font-size: $text-small;
  }

  .coverage,
  .warnings {
    font-size: $text-small;
    color: rgb(var(--v-theme-text-secondary));
    margin: $space-2 0;
  }

  .previewOptions {
    display: flex;
    gap: $space-2;
    margin-top: $space-2;
  }

  .visibility {
    max-width: 180px;
  }
}
</style>
