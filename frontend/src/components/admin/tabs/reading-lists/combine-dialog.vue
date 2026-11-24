<template>
  <v-dialog v-model="show" max-width="640px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">Combine Reading Lists</v-card-title>
      <v-card-text>
        <p class="adminProse">
          The chosen list's order wins. The others' sources join it and the
          others are deleted. Removing a source later undoes it.
        </p>
        <v-radio-group v-model="primary" density="compact" hide-details>
          <v-radio
            v-for="list in chosen"
            :key="list.pk"
            :value="list.pk"
            :label="`${list.name} (${list.total} issues)`"
          />
        </v-radio-group>
        <AdminKeyValueTable v-if="result" :items="resultRows" class="result" />
      </v-card-text>
      <v-card-actions>
        <!-- Why Combine is off, in words: a title never shows. -->
        <span v-if="disabledReason" class="combineHint">
          {{ disabledReason }}
        </span>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Cancel</v-btn>
        <v-btn
          variant="tonal"
          :disabled="Boolean(disabledReason)"
          :loading="working"
          @click="combine"
        >
          Combine
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapState } from "pinia";

import * as API from "@/api/v4/reading-lists";
import AdminKeyValueTable from "@/components/admin/tabs/key-value-table.vue";
import { useCommonStore } from "@/stores/common";
import { useReadingListsStore } from "@/stores/reading-lists";

export default {
  name: "CombineDialog",
  components: { AdminKeyValueTable },
  props: {
    modelValue: { type: Boolean, default: false },
    pks: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue", "combined"],
  data() {
    return { primary: null, result: null, working: false };
  },
  computed: {
    ...mapState(useReadingListsStore, ["listsByPk"]),
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
    chosen() {
      return this.pks.map((pk) => this.listsByPk[pk]).filter(Boolean);
    },
    others() {
      return this.pks.filter((pk) => pk !== this.primary);
    },
    disabledReason() {
      if (this.chosen.length < 2)
        return "Choose at least two lists to combine.";
      if (!this.primary) return "Choose the list whose order wins.";
      return "";
    },
    resultRows() {
      if (!this.result) return {};
      const rows = {
        "Issues in the combined list": this.result.total,
        "Joined on a name alone (check these)": this.result.nameJoins,
        "Order disagreements": this.result.orderConflicts,
        "Id disagreements": this.result.idConflicts,
      };
      for (const only of this.result.onlyIn || []) {
        const name = this.listsByPk[only.pk]?.name || only.pk;
        rows[`Only in ${name}`] = only.count;
      }
      return rows;
    },
  },
  watch: {
    modelValue: {
      immediate: true,
      handler(value) {
        if (!value) return;
        this.result = null;
        const primary = this.pks[0] || null;
        if (this.primary === primary) {
          // The same primary as last time: its watcher won't fire.
          this.dryRun();
        } else {
          this.primary = primary;
        }
      },
    },
    primary() {
      if (this.show) this.dryRun();
    },
  },
  methods: {
    async dryRun() {
      if (!this.primary || !this.others.length) return;
      try {
        const response = await API.combineLists(
          this.primary,
          this.others,
          true,
        );
        this.result = response.data;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      }
    },
    async combine() {
      this.working = true;
      try {
        await API.combineLists(this.primary, this.others, false);
        const name = this.listsByPk[this.primary]?.name || "the list";
        useCommonStore().setNotice(
          `Combined ${this.others.length + 1} lists into ${name}.`,
        );
        this.$emit("combined");
        this.show = false;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      } finally {
        this.working = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .result {
    margin-top: $space-4;
  }

  .combineHint {
    padding-left: $space-2;
    font-size: $text-small;
    color: rgb(var(--v-theme-text-secondary));
  }

  .dialogTitle {
    font-weight: bold;
  }
}
</style>
