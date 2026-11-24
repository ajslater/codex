<template>
  <v-menu
    v-if="isLoggedIn"
    v-model="menu"
    :close-on-content-click="false"
    :location="location"
    :submenu="submenu"
  >
    <template #activator="{ props: activatorProps }">
      <slot
        name="activator"
        :props="activatorProps"
        :on="on"
        :disabled="disabled"
      >
        <v-btn
          v-bind="{ ...$attrs, ...activatorProps }"
          class="listMenuButton"
          :class="{ listMenuOn: on, listMenuOpen: menu }"
          :icon="mdiPlaylistPlus"
          :title="title"
          :aria-label="title"
          :disabled="disabled"
          density="compact"
          size="small"
          variant="plain"
          @click.stop.prevent
        />
      </slot>
    </template>
    <!-- No header: every opener of this menu already says "Reading Lists". -->
    <v-sheet class="listMenu" @click.stop>
      <section class="listMenuSection">
        <v-text-field
          v-if="rows.length > FILTER_AFTER"
          v-model="query"
          class="listFilter"
          density="compact"
          hide-details
          clearable
          label="Find a list"
          variant="outlined"
          @click.stop
        />
        <v-list class="listMenuList" density="compact">
          <v-list-item
            v-for="row of shownRows"
            :key="row.pk"
            class="listMenuRow"
            density="compact"
            role="menuitemcheckbox"
            :aria-checked="row.ariaChecked"
            :title="row.name"
            :subtitle="row.personal ? '' : 'Global'"
            @click="onToggle(row)"
          >
            <template #prepend>
              <v-checkbox-btn
                density="compact"
                :indeterminate="row.state === 'some'"
                :model-value="row.state === 'all'"
                tabindex="-1"
                readonly
              />
            </template>
          </v-list-item>
          <v-list-item
            v-if="!creating"
            class="listMenuNew"
            density="compact"
            :prepend-icon="mdiPlus"
            title="New reading list…"
            @click="creating = true"
          />
        </v-list>
        <ListNameInput
          v-if="creating"
          class="listMenuNameInput"
          :error="createError"
          :existing-names="myListNames"
          submit-title="Create the list with these"
          @cancel="creating = false"
          @submit="onCreate"
        />
        <div class="listMenuHint">
          A series, folder or other group added whole keeps its comics current.
          Saved in Codex only: no comic file changes.
        </div>
      </section>
    </v-sheet>
  </v-menu>
</template>

<script>
import { mdiPlaylistPlus, mdiPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ListNameInput from "@/components/list-name-input.vue";
import { useAuthStore } from "@/stores/auth";
import { getErrors } from "@/stores/common";
import { useReadingListsStore } from "@/stores/reading-lists";

const ARIA_CHECKED = Object.freeze({
  all: "true",
  some: "mixed",
  none: "false",
});
// Past this many lists the menu grows a field to find one by name.
const FILTER_AFTER = 8;
const READING_LISTS = "arcs";

/*
 * The one menu that puts things in reading lists: on cards, table rows,
 * the selection toolbar, the metadata dialog and the reader. Each list the
 * user may change is a row whose checkbox says whether the targets are in
 * it directly; a click puts them in or takes them out, and the menu stays
 * open. Issues are added by hand; a whole collection stays current.
 */
export default {
  name: "ReadingListMenu",
  components: { ListNameInput },
  // The class and id a call site passes belong on the button, not on the
  // menu overlay VMenu would forward them to.
  inheritAttrs: false,
  props: {
    collection: {
      type: String,
      default: "",
    },
    /*
     * Single-target convenience prop (browser cards, table cells, the
     * reader). The metadata dialog passes ``pks`` instead for a whole
     * selection of one collection. Both normalize to ``targetMap``.
     */
    pk: {
      type: [Number, String],
      default: null,
    },
    pks: {
      type: Array,
      default: () => [],
    },
    /*
     * A ``{collection: [pks]}`` map for a selection that spans several
     * collection types (the multi-select toolbar). Wins over
     * ``collection`` + ``pk``/``pks`` when given.
     */
    targets: {
      type: Object,
      default: null,
    },
    /*
     * Which way the menu hangs off its activator. The default suits a
     * toolbar or table button; a browser card's action menu passes "end"
     * so the lists open beside it as a submenu.
     */
    location: {
      type: String,
      default: "bottom end",
    },
    // Inside another menu, so arrow keys move through the parent's items
    // instead of popping this one open.
    submenu: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      createError: "",
      creating: false,
      FILTER_AFTER,
      // One glyph either way; the accent color says "in a list".
      mdiPlaylistPlus,
      mdiPlus,
      menu: false,
      query: "",
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      // Anonymous sessions own no lists, so they get no list button.
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useReadingListsStore, [
      "editableLists",
      "isEveryListed",
      "membershipState",
      "myListNames",
      "myListsLoaded",
    ]),
    targetMap() {
      const source =
        this.targets ??
        (this.collection
          ? { [this.collection]: this.pks?.length ? this.pks : [this.pk] }
          : {});
      const map = {};
      for (const [collection, pks] of Object.entries(source)) {
        const numbers = (pks || [])
          .filter((pk) => pk !== null && pk !== undefined)
          .map(Number);
        if (numbers.length > 0) map[collection] = numbers;
      }
      return map;
    },
    targetCount() {
      let count = 0;
      for (const pks of Object.values(this.targetMap)) {
        count += pks.length;
      }
      return count;
    },
    on() {
      // Accented only when every target is directly in some list.
      return this.isEveryListed(this.targetMap);
    },
    title() {
      return this.targetCount > 1
        ? `Reading Lists for ${this.targetCount} items`
        : "Reading Lists";
    },
    disabled() {
      return this.targetCount === 0;
    },
    rows() {
      // A list is not offered as a place to put itself.
      const own = new Set(this.targetMap[READING_LISTS] || []);
      return this.editableLists
        .filter(({ pk }) => !own.has(pk))
        .map(({ pk, name, personal }) => {
          const state = this.membershipState(pk, this.targetMap);
          return {
            pk,
            name,
            personal,
            state,
            ariaChecked: ARIA_CHECKED[state],
          };
        });
    },
    shownRows() {
      const query = (this.query || "").trim().toLowerCase();
      if (!query) return this.rows;
      return this.rows.filter((row) => row.name.toLowerCase().includes(query));
    },
  },
  watch: {
    creating() {
      // Opening or closing the name input drops the last attempt's error.
      this.createError = "";
    },
    menu(to) {
      if (to && !this.myListsLoaded) {
        this.loadMyLists();
      }
      if (!to) {
        this.creating = false;
        this.createError = "";
        this.query = "";
      }
    },
  },
  methods: {
    ...mapActions(useReadingListsStore, [
      "createList",
      "loadMyLists",
      "setTargetsMembership",
    ]),
    onToggle(row) {
      // Mixed reads as off, so the first click adds the stragglers.
      const on = row.state !== "all";
      this.setTargetsMembership(row.pk, this.targetMap, on);
    },
    async onCreate(name) {
      this.createError = "";
      let list;
      try {
        list = await this.createList(name);
      } catch (error) {
        this.createError = getErrors(error).join(" ");
        return;
      }
      this.creating = false;
      if (list) await this.setTargetsMembership(list.pk, this.targetMap, true);
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .listMenuButton {
    color: rgb(var(--v-theme-text-secondary));
    opacity: 0.85;
  }

  .listMenuButton:hover {
    color: rgb(var(--v-theme-link-hover));
    opacity: 1;
  }

  .listMenuOn {
    color: rgb(var(--v-theme-primary));
    opacity: 1;
  }

  .listMenuOn:hover {
    color: rgb(var(--v-theme-link-hover));
  }

  .listMenu {
    min-width: 14em;
    max-width: 24em;
  }

  .listFilter {
    margin: 4px 12px;
  }

  .listMenuList {
    max-height: 50vh;
    overflow-y: auto;
    padding-top: 0;
  }

  .listMenuRow :deep(.v-list-item__prepend > .v-list-item__spacer),
  .listMenuNew :deep(.v-list-item__prepend > .v-list-item__spacer) {
    width: 8px;
  }

  .listMenuNameInput {
    padding: 4px 8px 10px 12px;
  }

  .listMenuHint {
    color: rgb(var(--v-theme-text-secondary));
    font-size: 0.8em;
    padding: 0 12px 8px;
    max-width: 22em;
  }
}
</style>
