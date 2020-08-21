<template>
  <v-dialog :value="isOpen">
    <v-btn></v-btn>
    <template #activator="{ on }">
      <v-btn
        ripple
        dense
        style="display: inline;"
        v-on="on"
        @click="metadata(pk)"
      >
        Metadata
      </v-btn>
    </template>
    <v-container v-if="comic">
      <v-img
        :src="'/static/' + comic.cover_path"
        lazy-src="/static/404.png"
        contain
        max-height="180px"
        max-width="180px"
        style="float: left;"
      />
      <div>
        {{ comic.header_name }}
      </div>
      <div>
        {{ comic.display_name }}
      </div>
      <table>
        <tr>
          <td>Date:</td>
          <td>{{ comic.year }}-{{ comic.month }}-{{ comic.day }}</td>
        </tr>
        <tr>
          <td>Format:</td>
          <td>{{ comic.format }}</td>
        </tr>
        <tr>
          <td>Pages:</td>
          <td>
            {{ comic.bookmark }} / {{ comic.page_count }} :
            {{ comic.finished }}
          </td>
        </tr>
        <tr>
          <td>Read Left to Right:</td>
          <td>{{ comic.read_ltr }}</td>
        </tr>
        <tr>
          <td>Size:</td>
          <td>{{ comic.size | bytes }}</td>
        </tr>
        <tr>
          <td>Country</td>
          <td>{{ comic.country }}</td>
        </tr>
        <tr>
          <td>Language</td>
          <td>{{ comic.language }}</td>
        </tr>
        <tr>
          <td>Web</td>
          <td><a :href="comic.web">Link</a></td>
        </tr>
        <tr>
          <td>User Rating</td>
          <td>{{ comic.user_rating }}</td>
        </tr>
        <tr>
          <td>Critical Rating</td>
          <td>{{ comic.critical_rating }}</td>
        </tr>
        <tr>
          <td>Maturity Rating</td>
          <td>{{ comic.maturity_rating }}</td>
        </tr>
        <tr>
          <td>Genres:</td>
          <td>
            <span v-for="genre in comic.genres" :key="genre.pk">{{
              genre.name
            }}</span>
          </td>
        </tr>
        <tr>
          <td>Tags:</td>
          <td>
            <span v-for="tag in comic.tags" :key="tag.pk">{{ tag.name }}</span>
          </td>
        </tr>
        <tr>
          <td>Teams:</td>
          <td>
            <span v-for="team in comic.teams" :key="team.pk">{{
              team.name
            }}</span>
          </td>
        </tr>
        <tr>
          <td>Characters:</td>
          <td>
            <span v-for="character in comic.characters" :key="character.pk">{{
              character.name
            }}</span>
          </td>
        </tr>
        <tr>
          <td>Locations:</td>
          <td>
            <span v-for="loc in comic.locations" :key="loc.pk">{{
              loc.name
            }}</span>
          </td>
        </tr>
        <tr>
          <td>Story Arcs:</td>
          <td>
            <span v-for="story_arc in comic.story_arcs" :key="story_arc.pk">{{
              story_arc.name
            }}</span>
          </td>
        </tr>
        <tr>
          <td>Series Groups:</td>
          <td>
            <span
              v-for="series_group in comic.series_goups"
              :key="series_group.pk"
              >{{ series_group.name }}</span
            >
          </td>
        </tr>
        <tr>
          <td>Fit To:</td>
          <td>{{ comic.fit_to }}</td>
        </tr>
        <tr>
          <td>Two Pages:</td>
          <td>{{ comic.two_pages }}</td>
        </tr>
        <tr>
          <td>Scan:</td>
          <td>{{ comic.scan }}</td>
        </tr>
        <tr>
          <td>
            <div>{{ comic.summary }}</div>
            <div>{{ comic.description }}</div>
            <div>{{ comic.notes }}</div>
          </td>
        </tr>
        <tr>
          <td>Credits:</td>
        </tr>
        <tr v-for="credit in comic.credits" :key="credit.pk">
          <td>{{ credit.role.name }}</td>
          <td>{{ credit.person.name }}</td>
        </tr>
      </table>
      <footer style="display: flex;">
        <a :href="downloadURL" download>Download</a>
        <router-link v-if="isBrowser()" :to="getReaderRoute(comic)">
          Read
        </router-link>
      </footer>
    </v-container>
  </v-dialog>
</template>
<script>
import { mapState } from "vuex";

import { getDownloadURL } from "@/api/metadata";
import { getReaderRoute } from "@/router/route";

export default {
  name: "MetadataButton",
  props: {
    pk: {
      type: Number,
      required: true,
      default: 0,
    },
  },
  data() {
    return {
      isOpen: false,
    };
  },
  computed: {
    ...mapState("metadata", {
      comic: (state) => state.comic,
    }),
  },
  methods: {
    metadata: function (pk) {
      this.$store.dispatch("metadata/comicMetadataOpened", pk);
      this.isOpen = true;
    },
    downloadURL: function () {
      return getDownloadURL(this.comic.pk);
    },
    isBrowser: function () {
      return this.$route.name === "browser";
    },
    getReaderRoute,
  },
};
</script>

<style scoped lang="scss"></style>
