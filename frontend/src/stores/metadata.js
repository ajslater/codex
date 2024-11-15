import { capitalCase } from "change-case-all";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

const ROLES = [
  "creators",
  "writers",
  "pencillers",
  "inkers",
  "cover_artists",
  "colorists",
  "letterers",
  "editors",
];
Object.freeze(ROLES);
const TAGS = [
  "genres",
  "characters",
  "teams",
  "locations",
  "seriesGroups",
  "stories",
  "storyArcNumbers",
  "tags",
];
Object.freeze(TAGS);

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  getters: {
    _mappedContributors(state) {
      const contributors = {};
      if (!state?.md?.contributors) {
        return contributors;
      }

      // Convert contributors into a role based map
      for (const { role, person } of state.md.contributors) {
        const roleName = role.name + "s";
        if (!(roleName in contributors)) {
          contributors[roleName] = [];
        }
        contributors[roleName].push(person);
      }
      return contributors;
    },
    _sortedRoles(state) {
      // Sort the roles by known order and then alphabetically.
      let sortedRoles = [];
      const roles = new Set(Object.keys(state._mappedContributors));
      for (const role of ROLES) {
        if (roles.has(role)) {
          sortedRoles.push(role);
          roles.delete(role);
        }
      }
      const tailRoles = [...roles].sort();
      return [...sortedRoles, ...tailRoles];
    },
    contributors(state) {
      return this.mapTag(
        state._mappedContributors,
        state._sortedRoles,
        "contributors",
      );
    },
    tags(state) {
      return state.mapTag(state.md, TAGS);
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
    mapTag(tagSource, keys, fixedFilter) {
      const tagMap = {};

      for (const key of keys) {
        let tags = tagSource[key];
        if (!tags?.length) {
          continue;
        }

        // Special sub
        let filter;
        if (fixedFilter) {
          filter = fixedFilter;
        } else if (key === "storyArcNumbers") {
          filter = "storyArcs";
        } else {
          filter = key;
        }
        const tagName = capitalCase(key);
        tags = tags.sort((a, b) => a.name.localeCompare(b.name));
        tagMap[tagName] = { filter, tags };
      }
      return tagMap;
    },
  },
});
