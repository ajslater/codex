import { defineStore } from "pinia";
import { capitalCase } from "text-case";

import * as API from "@/api/v4/browser";

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
const MAIN_TAGS = Object.freeze(new Set(["Characters", "Teams"]));

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
     * Display label rule (preserved from the v3 frontend): show
     * ``displayName:code`` when ``displayName`` is set, else just code.
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
    tags(state) {
      const tags = state.mapTag(state.md, TAGS);

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
    async loadMetadata({ group, pks }) {
      await API.getMetadata({ group, pks }, useBrowserStore().metadataSettings)
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
    /*
     *labelUniverses(tags) {
     *  for (const tag of tags) {
     *    tag.name += ` (${tag.designation})`;
     *  }
     *},
     */
    markTagMain(tagName, tags) {
      const attr = "main" + tagName.slice(0, -1);
      const mainPk = this.md[attr]?.pk;
      const regularTags = [];
      var mainTags = [];
      for (const tag of tags) {
        if (mainPk === tag.pk) {
          mainTags.push(tag);
        } else {
          regularTags.push(tag);
        }
      }
      return { mainTags, regularTags };
    },
    mapTag(tagSource, keys, filter = undefined) {
      const tagMap = {};

      for (const key of keys) {
        const tags = tagSource[key];
        if (!tags?.length) {
          continue;
        }
        const tagName = this.getTagName(key);

        var mainTags = [];
        var regularTags = [];
        /*
         *if (tagName === "Universes") {
         *  this.labelUniverses(tags);
         *  regularTags = tags;
         *} else
         */
        if (MAIN_TAGS.has(tagName)) {
          ({ mainTags, regularTags } = this.markTagMain(tagName, tags));
        } else {
          regularTags = tags;
        }

        filter = filter ? filter : key;

        tagMap[tagName] = { filter, tags: regularTags, mainTags };
      }
      return tagMap;
    },
    lazyImport({ group, ids }) {
      return API.getLazyImport({ group, pks: ids });
    },
  },
});
