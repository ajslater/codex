import { defineStore } from "pinia";
import { capitalCase } from "text-case";

import { abortKey, isAbortError, useAbortable } from "@/api/v4/abortable";
import { getTagNames } from "@/api/v4/admin";
import * as API from "@/api/v4/browser";
import { useBrowserStore } from "@/stores/browser";

const TAGS = Object.freeze([
  "genres",
  "characters",
  // identifiers
  "teams",
  "locations",
  // reprints, split into two rows by alternativeName
  "seriesGroups",
  "stories",
  "storyArcNumbers",
  "tags",
  "universes",
]);

// Rows whose display name isn't the capital-cased key.
const TAG_NAMES = Object.freeze({
  storyArcNumbers: "Story Arcs",
});

/*
 * Tag editor name suggestions.
 *
 * Cached per field, then per hierarchy scope (the form's parent names), then
 * per normalized query. The server returns at most a capped page of names
 * that *contain* the query, plus whether that page is every match. Every name
 * containing "batm" contains "bat", so a complete result for a shorter prefix
 * of the query already holds every answer and Vuetify's own filter narrows
 * it: typing past a complete prefix costs no request.
 */
const tagNamesAbortKey = (field) => `metadata:tagNames:${field}`;

const normalizeQuery = (q = "") => String(q).trim();
const queryKey = (q) => normalizeQuery(q).toLowerCase();

const BLANK_SCOPE_VALUES = Object.freeze(new Set(["", null, undefined]));

// The non-blank scope entries, in a stable order.
function scopeEntries(scope) {
  return Object.entries(scope || {})
    .filter(([, value]) => !BLANK_SCOPE_VALUES.has(value))
    .map(([key, value]) => [key, String(value)])
    .sort(([a], [b]) => a.localeCompare(b));
}

const scopeKey = (scope) => JSON.stringify(scopeEntries(scope));

/*
 * The cached result for the query or, failing that, for its longest cached
 * shorter prefix. With ``requiresComplete`` a shorter prefix only counts when
 * it is complete, which is when it can stand in for the query's own result.
 */
function findCachedNames(byQuery, qKey, requiresComplete = false) {
  if (!byQuery) return;
  for (let len = qKey.length; len >= 0; len--) {
    const entry = byQuery[qKey.slice(0, len)];
    if (!entry) continue;
    if (!requiresComplete || len === qKey.length || entry.complete) {
      return entry;
    }
  }
}

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
    // tagNames[field][scopeKey][queryKey] = {names, complete}
    tagNames: {},
    // tagNamesLoading[field] = true while that field's request is in flight
    tagNamesLoading: {},
  }),
  getters: {
    /*
     * Suggested names for a tag editor field. While a query's own request is
     * in flight its longest cached prefix stands in, complete or not, so the
     * menu isn't emptied on every keystroke. Vuetify filters and sorts.
     */
    tagNameChoices(state) {
      return (field, scope, q) => {
        const byQuery = state.tagNames[field]?.[scopeKey(scope)];
        return findCachedNames(byQuery, queryKey(q))?.names ?? [];
      };
    },
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
     * Reprints and the series' other names share one table and arrive in
     * one list, flagged. They mean different things to a reader — another
     * edition versus another title for this one — so they show as two
     * rows.
     */
    reprintRows(state) {
      const rows = state.md?.reprints;
      if (!Array.isArray(rows)) return {};
      const reprints = rows.filter((row) => !row.alternativeName);
      const alternativeNames = rows.filter((row) => row.alternativeName);
      const tagMap = {};
      if (reprints.length > 0) {
        tagMap["Reprints"] = { filter: "reprints", tags: reprints };
      }
      if (alternativeNames.length > 0) {
        tagMap["Alternative Names"] = {
          filter: "reprints",
          tags: alternativeNames,
        };
      }
      return tagMap;
    },
    /*
     * The links the file itself carries, minus the ones already shown as
     * identifier chips: codex derives those from a key, so showing both
     * would list the same page twice under two names.
     */
    webUrls(state) {
      const urls = state.md?.urls;
      if (!Array.isArray(urls)) return [];
      const shown = new Set(this.identifiers.map((item) => item.url));
      return urls
        .filter((url) => url && !shown.has(url))
        .map((url) => ({ name: url, url }));
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
      if (state.protagonists.length > 0) {
        tags["Protagonist"] = { filter: "", tags: state.protagonists };
      }
      Object.assign(tags, state.mapTag(state.md, TAGS));

      if (state.identifiers?.length) {
        tags["Identifiers"] = {
          filter: "identifiers",
          tags: this.identifiers,
        };
      }
      if (state.webUrls?.length) {
        tags["Web"] = { filter: "", tags: state.webUrls };
      }
      Object.assign(tags, state.reprintRows);
      for (const tagObj of Object.values(tags)) {
        // Sort a copy: sorting in place would mutate store state in a getter.
        tagObj.tags = [...tagObj.tags].sort((a, b) =>
          a.name.localeCompare(b.name),
        );
      }
      return tags;
    },
  },
  actions: {
    async loadMetadata({ collection, pks }) {
      try {
        const response = await API.getMetadata(
          { collection, pks },
          useBrowserStore().metadataSettings,
        );
        const md = { ...response.data, loaded: true };
        this.md = md;
      } catch (error) {
        console.error(error);
        this.clearMetadata();
      }
    },
    clearMetadata() {
      this.md = undefined;
      this.clearTagNames();
    },
    async loadTagNames({ field, scope = {}, q = "" }) {
      const sKey = scopeKey(scope);
      const qKey = queryKey(q);
      if (findCachedNames(this.tagNames[field]?.[sKey], qKey, true)) return;
      // One request per field: a newer query aborts the stale one.
      const signal = useAbortable(tagNamesAbortKey(field));
      this.tagNamesLoading[field] = true;
      try {
        const params = Object.fromEntries(scopeEntries(scope));
        params.q = normalizeQuery(q);
        const response = await getTagNames(field, params, { signal });
        const { names, complete } = response.data;
        this.tagNames[field] ??= {};
        this.tagNames[field][sKey] ??= {};
        this.tagNames[field][sKey][qKey] = Object.freeze({
          names: Object.freeze([...names]),
          complete: Boolean(complete),
        });
      } catch (error) {
        if (!isAbortError(error)) console.error(error);
      } finally {
        // An aborted request's successor owns the loading flag.
        if (!signal.aborted) this.tagNamesLoading[field] = false;
      }
    },
    /*
     * Names only change on a re-import, so the cache lives as long as the
     * editor: stale until it is reopened.
     */
    clearTagNames() {
      for (const field of Object.keys(this.tagNamesLoading)) {
        abortKey(tagNamesAbortKey(field));
      }
      this.tagNames = {};
      this.tagNamesLoading = {};
    },
    getTagName(key) {
      return TAG_NAMES[key] || capitalCase(key);
    },
    mapTag(tagSource, keys, filter) {
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
