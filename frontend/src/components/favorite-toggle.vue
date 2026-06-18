<template>
  <v-btn
    class="favoriteToggle"
    :class="{ favoriteToggleOn: on }"
    :icon="icon"
    :title="title"
    :aria-label="title"
    :aria-pressed="on"
    :disabled="disabled"
    density="compact"
    size="small"
    variant="plain"
    @click.stop.prevent="onClick"
  />
</template>

<script>
import { mdiStar, mdiStarOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useFavoritesStore } from "@/stores/favorites";

export default {
  name: "FavoriteToggle",
  props: {
    collection: {
      type: String,
      required: true,
    },
    /*
     * Single-target convenience prop (browser cards). The metadata
     * toolbar passes ``pks`` instead to favorite a whole multi-select.
     * Exactly one of ``pk`` / ``pks`` is expected; both normalize to
     * ``targetPks``.
     */
    pk: {
      type: [Number, String],
      default: null,
    },
    pks: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useFavoritesStore, ["isFavorite"]),
    targetPks() {
      const source = this.pks?.length ? this.pks : [this.pk];
      return source.filter((pk) => pk !== null && pk !== undefined).map(Number);
    },
    isBulk() {
      return this.targetPks.length > 1;
    },
    on() {
      // Filled only when every target is favorited (mixed reads as off,
      // so the first click favorites the stragglers).
      return (
        this.targetPks.length > 0 &&
        this.targetPks.every((pk) => this.isFavorite(this.collection, pk))
      );
    },
    icon() {
      return this.on ? mdiStar : mdiStarOutline;
    },
    title() {
      const verb = this.on ? "Remove" : "Add";
      if (this.isBulk) {
        const preposition = this.on ? "from" : "to";
        return `${verb} ${this.targetPks.length} ${preposition} Favorites`;
      }
      return this.on ? "Remove from Favorites" : "Add to Favorites";
    },
    disabled() {
      /*
       * Anonymous sessions can't favorite — the API rejects with 403.
       * Hide the affordance rather than letting the user click into
       * an error.
       */
      return !this.isLoggedIn || this.targetPks.length === 0;
    },
  },
  methods: {
    ...mapActions(useFavoritesStore, ["toggle", "setManyFavorites"]),
    onClick() {
      if (this.disabled) return;
      if (this.isBulk) {
        this.setManyFavorites(this.collection, this.targetPks, !this.on);
      } else {
        this.toggle(this.collection, this.targetPks[0]);
      }
    },
  },
};
</script>

<style scoped lang="scss">
.favoriteToggle {
  color: rgb(var(--v-theme-textSecondary));
  opacity: 0.85;
}

.favoriteToggle:hover {
  color: rgb(var(--v-theme-linkHover));
  opacity: 1;
}

.favoriteToggleOn {
  color: rgb(var(--v-theme-primary));
  opacity: 1;
}

.favoriteToggleOn:hover {
  color: rgb(var(--v-theme-linkHover));
}
</style>
