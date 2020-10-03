<template>
  <v-select
    v-model="sortBy"
    class="toolbarSelect sortBySelect"
    :items="sortChoices"
    prefix="by "
    dense
    hide-details="auto"
    ripple
  >
    <template #item="data">
      <v-list-item v-bind="data.attrs" v-on="data.on">
        <v-list-item-content>
          <v-list-item-title>
            {{ data.item.text }}
            <v-icon
              v-show="sortBy === data.item.value"
              class="sortArrow"
              :class="{ upsideDown: !sortReverseSetting }"
            >
              {{ mdiArrowUp }}
            </v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
  </v-select>
</template>

<script>
import { mdiArrowUp } from "@mdi/js";
import { mapState } from "vuex";

export default {
  name: "BrowseSortBySelect",
  components: {},
  data() {
    return {
      mdiArrowUp,
    };
  },
  computed: {
    ...mapState("browser", {
      sortChoices: (state) => state.formChoices.sort,
      sortReverseSetting: (state) => state.settings.sortReverse,
      sortBySetting: (state) => state.settings.sortBy,
    }),
    sortBy: {
      get() {
        return this.sortBySetting;
      },
      set(value) {
        let data = {};
        if (value === this.sortBySetting) {
          data.sortReverse = !this.sortReverseSetting;
        } else {
          data.sortReverse = false;
          data.sortBy = value;
        }
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
  methods: {},
};
</script>

<style scoped lang="scss">
.sortArrow {
  width: 20px;
  float: right;
}
.upsideDown {
  transform: rotate(180deg);
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
.sortBySelect {
  width: 168px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .sortBySelect {
    width: 133px;
    margin-right: -19px;
  }
}
</style>
