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
    group: {
      type: String,
      required: true,
    },
    pk: {
      type: [Number, String],
      required: true,
    },
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useFavoritesStore, ["isFavorite"]),
    on() {
      return this.isFavorite(this.group, Number(this.pk));
    },
    icon() {
      return this.on ? mdiStar : mdiStarOutline;
    },
    title() {
      return this.on ? "Remove from Favorites" : "Add to Favorites";
    },
    disabled() {
      /*
       * Anonymous sessions can't favorite — the API rejects with 403.
       * Hide the affordance rather than letting the user click into
       * an error.
       */
      return !this.isLoggedIn;
    },
  },
  methods: {
    ...mapActions(useFavoritesStore, ["toggle"]),
    onClick() {
      if (this.disabled) return;
      this.toggle(this.group, Number(this.pk));
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
