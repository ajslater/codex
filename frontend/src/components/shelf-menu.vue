<template>
  <v-menu
    v-if="isLoggedIn"
    v-model="menu"
    :close-on-content-click="false"
    location="bottom end"
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
          class="shelfMenuButton"
          :class="{ shelfMenuOn: on, shelfMenuOpen: menu }"
          :icon="icon"
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
    <v-sheet class="shelfMenu" @click.stop>
      <!--
        One titled section per kind of grouping. Another kind (reading
        lists) is a second MenuSection after this one.
      -->
      <MenuSection title="Shelves">
        <v-list class="shelfMenuList" density="compact">
          <v-list-item
            v-for="shelf of shelfRows"
            :key="shelf.pk"
            class="shelfMenuRow"
            density="compact"
            role="menuitemcheckbox"
            :aria-checked="shelf.ariaChecked"
            :title="shelf.name"
            @click="onToggle(shelf)"
          >
            <template #prepend>
              <v-checkbox-btn
                density="compact"
                :indeterminate="shelf.state === 'some'"
                :model-value="shelf.state === 'all'"
                tabindex="-1"
                readonly
              />
            </template>
          </v-list-item>
          <v-list-item
            v-if="!creating"
            class="shelfMenuNew"
            density="compact"
            :prepend-icon="mdiPlus"
            title="New shelf…"
            @click="creating = true"
          />
        </v-list>
        <ShelfNameInput
          v-if="creating"
          class="shelfMenuNameInput"
          :error="createError"
          :existing-names="shelfNames"
          @cancel="creating = false"
          @submit="onCreate"
        />
      </MenuSection>
    </v-sheet>
  </v-menu>
</template>

<script>
import { mdiBookmarkBox, mdiBookmarkBoxOutline, mdiPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import MenuSection from "@/components/menu-section.vue";
import ShelfNameInput from "@/components/shelf-name-input.vue";
import { useAuthStore } from "@/stores/auth";
import { useShelvesStore } from "@/stores/shelves";

const ARIA_CHECKED = Object.freeze({
  all: "true",
  some: "mixed",
  none: "false",
});

export default {
  name: "ShelfMenu",
  components: { MenuSection, ShelfNameInput },
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
     * reader). The metadata toolbar passes ``pks`` instead to shelve a
     * whole selection of one collection. Both normalize to ``targetMap``.
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
  },
  data() {
    return {
      createError: "",
      creating: false,
      mdiPlus,
      menu: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      /*
       * Anonymous sessions have no shelves — the API rejects them with
       * 403 — so they get no shelf affordance at all.
       */
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useShelvesStore, [
      "isEveryShelved",
      "membershipState",
      "shelfNames",
      "shelves",
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
      // Accented only when every target is on at least one shelf.
      return this.isEveryShelved(this.targetMap);
    },
    icon() {
      return this.on ? mdiBookmarkBox : mdiBookmarkBoxOutline;
    },
    title() {
      return this.targetCount > 1
        ? `Shelves for ${this.targetCount} items`
        : "Shelves";
    },
    disabled() {
      return this.targetCount === 0;
    },
    shelfRows() {
      return this.shelves.map(({ pk, name }) => {
        const state = this.membershipState(pk, this.targetMap);
        return { pk, name, state, ariaChecked: ARIA_CHECKED[state] };
      });
    },
  },
  watch: {
    menu(to) {
      if (!to) {
        this.creating = false;
        this.createError = "";
      }
    },
  },
  methods: {
    ...mapActions(useShelvesStore, ["createShelf", "setTargetsMembership"]),
    onToggle(shelf) {
      // Mixed reads as off, so the first click shelves the stragglers.
      const on = shelf.state !== "all";
      this.setTargetsMembership(shelf.pk, this.targetMap, on);
    },
    async onCreate(name) {
      this.createError = "";
      const shelf = await this.createShelf(name);
      if (!shelf) {
        this.createError = "Could not create shelf";
        return;
      }
      this.creating = false;
      await this.setTargetsMembership(shelf.pk, this.targetMap, true);
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .shelfMenuButton {
    color: rgb(var(--v-theme-text-secondary));
    opacity: 0.85;
  }

  .shelfMenuButton:hover {
    color: rgb(var(--v-theme-link-hover));
    opacity: 1;
  }

  .shelfMenuOn {
    color: rgb(var(--v-theme-primary));
    opacity: 1;
  }

  .shelfMenuOn:hover {
    color: rgb(var(--v-theme-link-hover));
  }

  .shelfMenu {
    min-width: 14em;
    max-width: 24em;
  }

  .shelfMenuList {
    max-height: 50vh;
    overflow-y: auto;
    padding-top: 0;
  }

  .shelfMenuRow :deep(.v-list-item__prepend > .v-list-item__spacer),
  .shelfMenuNew :deep(.v-list-item__prepend > .v-list-item__spacer) {
    width: 8px;
  }

  .shelfMenuNameInput {
    padding: 4px 8px 10px 12px;
  }
}
</style>
