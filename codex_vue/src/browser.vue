<template>
  <div>
    <v-toolbar dense>
      <v-menu :close-on-content-click="false" offset-y bottom>
        <template v-slot:activator="{ on }">
          <v-btn v-on="on">
            Filter
          </v-btn>
        </template>
        <v-list dense style="max-height: 90vh;" class="overflow-y-auto">
          <v-list-item-group v-model="bookmarkFilter" mandatory>
            <v-list-item
              v-for="item of staticFormChoices.bookmarkFilterChoices"
              :key="item.value"
              :value="item.value"
            >
              <v-list-item-content>
                <v-list-item-title v-text="item.text" />
              </v-list-item-content>
            </v-list-item>
          </v-list-item-group>
          <v-list-group sub-group>
            <template v-slot:activator>
              <v-list-item-title>Decade</v-list-item-title>
            </template>

            <v-list-item-group v-model="decadeFilter" multiple dense>
              <v-list-item
                v-for="item of formChoices.decadeFilterChoices"
                :key="item.value"
                :value="item.value"
              >
                <v-list-item-content>
                  <v-list-item-title v-text="item.text" />
                </v-list-item-content>
              </v-list-item>
            </v-list-item-group>
          </v-list-group>
          <v-list-group sub-group>
            <template v-slot:activator>
              <v-list-item-title>Character</v-list-item-title>
            </template>

            <v-list-item-group v-model="charactersFilter" multiple dense>
              <v-list-item
                v-for="item of formChoices.charactersFilterChoices"
                :key="item.value"
                :value="item.value"
              >
                <v-list-item-content>
                  <v-list-item-title v-text="item.text" />
                </v-list-item-content>
              </v-list-item>
            </v-list-item-group>
          </v-list-group>
        </v-list>
      </v-menu>
      <v-flex shrink>
        <v-select
          id="rootGroupSelect"
          v-model="rootGroup"
          class="toolbarSelect"
          label="Group"
          :items="rootGroupChoices"
          dense
          mandatory
          solo
        />
      </v-flex>
      <v-flex shrink>
        <v-select
          id="sortBySelect"
          v-model="sortBy"
          class="toolbarSelect"
          :items="staticFormChoices.sortChoices"
          label="Sort"
          mandatory
          dense
          solo
        />
      </v-flex>
      <v-checkbox v-model="sortReverse" label="reverse" />
      <v-spacer />
      <v-dialog
        origin="center-top"
        transition="slide-y-transition"
        max-width="20em"
        overlay-opacity="0.5"
      >
        Settings
        <template #activator="{ on }">
          <v-btn icon v-on="on">
            <v-icon>{{ mdiCog }}</v-icon>
          </v-btn>
        </template>
        <v-checkbox
          v-for="choice of staticFormChoices.settingsGroupChoices"
          :key="choice.value"
          :input-value="getShow(choice.value)"
          :label="`Show ${choice.text}`"
          dense
          @change="setShow(choice.value, $event)"
        />
        <v-btn v-if="isAdmin" ripple href="/admin/">
          Admin Panel
        </v-btn>
      </v-dialog>
      <AuthButton />
    </v-toolbar>
    <header>
      <section class="display-2 font-weight-bold text-center">
        <span>{{ browseTitle }}</span>
      </section>
      <router-link
        v-if="upRoute && upRoute.group"
        :to="{ name: 'browser', params: upRoute }"
        >Up</router-link
      >
    </header>
    <main id="browsePane">
      <v-lazy
        v-for="item in containerList"
        :key="item.pk"
        class="browseCardWrapper"
        transition="scale-transition"
      >
        <v-card
          :to="{ name: 'browser', params: { group: item.group, pk: item.pk } }"
          tile
          ripple
          class="browseTile"
        >
          <v-img
            :src="'/static/' + item.cover_path"
            lazy-src="/static/404.png"
            contain
            class="coverPage"
          />
          <v-progress-linear
            :value="item.progress"
            rounded
            background-color="inherit"
          />
          <v-card-subtitle class="cardSubtitle">
            {{ item.display_name }} ({{ item.child_count }})
          </v-card-subtitle>
          <v-checkbox
            label="read"
            :input-value="item.finished"
            :indeterminate="item.finished === null"
            class="readCheckbox"
            @change="markRead(item.group, item.pk, $event === true)"
          />
        </v-card>
      </v-lazy>
      <v-lazy
        v-for="item in comicList"
        :key="item.pk"
        class="browseCardWrapper"
        transition="scale-transition"
      >
        <v-card tile ripple class="browseTile">
          <router-link :to="getReaderRoute(item)">
            <v-img
              :src="'/static/' + item.cover_path"
              lazy-src="/static/404.png"
              contain
              class="coverPage"
            />
            <v-progress-linear
              :value="item.progress"
              background-color="inherit"
              rounded
            />
            <v-card-subtitle class="cardSubtitle">
              {{ item.header_name }}<br />
              {{ item.display_name }}
            </v-card-subtitle>
          </router-link>
          <footer style="display: flex;">
            <v-checkbox
              :input-value="item.finished"
              label="read"
              class="readCheckbox"
              @change="markRead(item.group, item.pk, $event)"
            />
            <MetadataButton :pk="item.pk" />
          </footer>
        </v-card>
      </v-lazy>
    </main>
  </div>
</template>

<script>
import { mdiChevronRight, mdiCog } from "@mdi/js";
import { mapState } from "vuex";

import { getSocket } from "@/api/browser";
import FORM_CHOICES from "@/choices/browserChoices.json";
import AuthButton from "@/components/auth-dialog";
import MetadataButton from "@/components/metadata-dialog";
import { getReaderRoute } from "@/router/route";
import { ROOT_GROUP_FLAGS } from "@/store/modules/browser";

export default {
  name: "Browser",
  components: {
    AuthButton,
    MetadataButton,
  },
  data() {
    return {
      mdiCog,
      mdiChevronRight,
      staticFormChoices: FORM_CHOICES,
      socket: undefined,
    };
  },
  computed: {
    ...mapState("browser", {
      browseTitle: (state) => state.browseTitle,
      currentRoute: (state) => state.routes.current,
      formChoices: (state) => state.formChoices,
      settings: (state) => state.settings,
      upRoute: (state) => state.routes.up,
      containerList: (state) => state.containerList,
      comicList: (state) => state.comicList,
    }),
    ...mapState("auth", {
      isAdmin: (state) => state.user && state.user.is_staff,
    }),
    bookmarkFilter: {
      get() {
        return this.settings.bookmarkFilter;
      },
      set(value) {
        this.settingChanged({ bookmarkFilter: value });
      },
    },
    decadeFilter: {
      get() {
        return this.settings.decadeFilter;
      },
      set(value) {
        this.settingChanged({ decadeFilter: value });
      },
    },
    charactersFilter: {
      get() {
        return this.settings.charactersFilter;
      },
      set(value) {
        this.settingChanged({ charactersFilter: value });
      },
    },
    rootGroup: {
      get() {
        return this.settings.rootGroup;
      },
      set(value) {
        this.settingChanged({ rootGroup: value });
      },
    },
    sortBy: {
      get() {
        return this.settings.sortBy;
      },
      set(value) {
        this.settingChanged({ sortBy: value });
      },
    },
    sortReverse: {
      get() {
        return this.settings.sortReverse;
      },
      set(value) {
        this.settingChanged({ sortReverse: value === true });
      },
    },
    rootGroupChoices: function () {
      const choices = [];
      for (let item of Object.values(FORM_CHOICES.rootGroupChoices)) {
        const [key, flag] = ROOT_GROUP_FLAGS[item.value];
        const enable = this[key].show[flag];
        if (enable) {
          choices.push(item);
        }
      }
      return Object.values(choices);
    },
  },
  watch: {
    $route(to) {
      this.$store.dispatch("browser/routeChanged", to.params);
    },
  },
  beforeCreate() {},
  created() {
    this.$store.dispatch("browser/browseOpened", this.$route.params);
    this.socket = getSocket();
    this.socket.addEventListener("message", (event) => {
      if (event.data === "libraryChanged") {
        this.$store.dispatch("browser/browseOpened", this.$route.params);
      }
    });
  },
  beforeDestroy() {
    if (this.socket) {
      this.socket.close();
    }
  },
  methods: {
    getShow: function (group) {
      return this.settings.show[group];
    },
    setShow: function (group, value) {
      const data = { show: { [group]: value === true } };
      this.$store.dispatch("browser/settingChanged", data);
    },
    settingChanged: function (data) {
      this.$store.dispatch("browser/settingChanged", data);
    },
    markRead: function (group, pk, finished) {
      this.$store.dispatch("browser/markRead", { group, pk, finished });
    },
    getReaderRoute,
  },
};
</script>

<style scoped lang="scss">
#browsePane {
  height: 100%;
  width: 100%;
}
.coverPage {
  height: 180px;
  max-width: 180px;
}
.browseTile {
  width: 200px;
  height: 260px;
  float: left;
  padding: 15px;
}
.readCheckbox {
  padding: 0px;
  margin: 0px;
}
.cardSubtitle {
  padding: 0px;
}
.toolbarSelect {
  width: 14em;
}
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
/* TODO SCOPE */
.scale-transition-enter-active,
.scale-transition-leave-active {
  transition: all 0.1s ease-out;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
