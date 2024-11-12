import { capitalCase } from "change-case-all";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

const ROLE_ORDER = [
  "Creators",
  "Writers",
  "Pencillers",
  "Inkers",
  "Cover Artists",
  "Colorists",
  "Letterers",
  "Editors",
];
Object.freeze(ROLE_ORDER);

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  getters: {
    contributors() {
      const contributors = {};
      if (!this?.md?.contributors) {
        return contributors;
      }

      // Convert contributors into a role based map
      for (const { role, person } of this.md.contributors) {
        const roleName = capitalCase(role.name) + "s";
        if (!contributors[roleName]) {
          contributors[roleName] = [];
        }
        contributors[roleName].push(person);
      }

      // Sort the roles
      let sortedRoles = [];
      const roles = new Set(Object.keys(contributors));
      for (const role of ROLE_ORDER) {
        if (roles.has(role)) {
          sortedRoles.push(role);
          roles.delete(role);
        }
      }
      const tailRoles = Array.from(roles).sort();
      sortedRoles = sortedRoles.concat(tailRoles);

      // Reconstruct the map based on the sorted roles;
      const sortedContributors = {};
      for (const roleName of sortedRoles) {
        const persons = contributors[roleName];
        sortedContributors[roleName] = persons.sort((a, b) =>
          a.name.localeCompare(b.name),
        );
      }

      return sortedContributors;
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
  },
});
