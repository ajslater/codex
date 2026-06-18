import { defineStore } from "pinia";
import { capitalCase } from "text-case";

import * as API from "@/api/v4/browser";
import { useBrowserStore } from "@/stores/browser";

const TAGS = Object.freeze([
  "genres",
  "characters",
  // identifiers
  "teams",
  "locations",
  "seriesGroups",
  "stories",
  "storyArcNumbers",
  "tags",
  "universes",
]);

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  getters: {
    /*
     * v4 ships credits already pivoted to ``{role: [{pk, name, url}]}``
     * with roles in HEAD_ROLES precedence and persons last-name sorted
     * (see ``codex/serializers/v4/metadata.py``). The client just
     * needs to wrap it for the existing ``mapTag`` consumer.
     */
    credits(state) {
      const grouped = state?.md?.credits;
      if (!grouped || typeof grouped !== "object") return {};
      const roles = Object.keys(grouped);
      return this.mapTag(grouped, roles, "credits");
    },
    /*
     * v4 ships identifiers as ``[{pk, type, code, displayName, url}]``.
     * Display label rule: show ``displayName:code`` when ``displayName``
     * is set, else just code.
     */
    identifiers(state) {
      const items = [];
      const rows = state.md?.identifiers;
      if (!Array.isArray(rows)) return items;
      for (const row of rows) {
        const label = row.displayName
          ? `${row.displayName}:${row.code}`
          : row.code;
        items.push({ pk: row.pk, url: row.url, name: label });
      }
      return items;
    },
    /*
     * The protagonist is stored as mainCharacter XOR mainTeam — both
     * filled should never happen, but display both if it does. Each
     * chip carries its own browser filter key so the character chip
     * filters characters and the team chip filters teams.
     */
    protagonists(state) {
      const protagonists = [];
      if (state.md?.mainCharacter) {
        protagonists.push({ ...state.md.mainCharacter, filter: "characters" });
      }
      if (state.md?.mainTeam) {
        protagonists.push({ ...state.md.mainTeam, filter: "teams" });
      }
      return protagonists;
    },
    tags(state) {
      const tags = {};
      if (state.protagonists.length) {
        tags["Protagonist"] = { filter: "", tags: state.protagonists };
      }
      Object.assign(tags, state.mapTag(state.md, TAGS));

      if (state.identifiers?.length) {
        tags["Identifiers"] = {
          filter: "identifiers",
          tags: this.identifiers,
        };
      }
      for (const tagObj of Object.values(tags)) {
        tagObj.tags = tagObj.tags.sort((a, b) => a.name.localeCompare(b.name));
      }
      return tags;
    },
  },
  actions: {
    async loadMetadata({ collection, pks }) {
      await API.getMetadata(
        { collection, pks },
        useBrowserStore().metadataSettings,
      )
        .then((response) => {
          const md = { ...response.data };
          md.loaded = true;
          this.md = md;
          return true;
        })
        .catch((error) => {
          console.error(error);
          this.clearMetadata();
        });
    },
    clearMetadata() {
      this.md = undefined;
    },
    getTagName(key) {
      var tagName;
      if (key === "storyArcNumbers") {
        tagName = "Story Arcs";
      } else {
        tagName = capitalCase(key);
      }
      return tagName;
    },
    mapTag(tagSource, keys, filter = undefined) {
      const tagMap = {};

      for (const key of keys) {
        const tags = tagSource[key];
        if (!tags?.length) {
          continue;
        }
        const tagName = this.getTagName(key);
        tagMap[tagName] = { filter: filter || key, tags };
      }
      return tagMap;
    },
    lazyImport({ collection, ids }) {
      return API.getLazyImport({ collection, pks: ids });
    },
  },
});
