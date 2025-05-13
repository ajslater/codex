import { capitalCase } from "change-case-all";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import { useBrowserStore } from "@/stores/browser";

const HEAD_ROLES = [
  // writer
  "writer",
  "author",
  "plotter",
  "plot",
  "script",
  "scripter",
  "story",
  "interviewer",
  "translator",
  // art
  "artist",
  // pencil
  "penciller",
  "breakdowns",
  "pencils",
  "illustrator",
  "layouts",
  // ink
  "inker",
  "finishes",
  "inks",
  "embellisher",
  "inkAssists",
  // color
  "colorist",
  "colorer",
  "colourer",
  "colors",
  "colours",
  "colorDesigner",
  "colorFlats",
  "colorSeparations",
  "designer",
  "digitalArtTechnician",
  "grayTone",
  // letters
  "letterer",
  // cover
  "cover",
  "covers",
  "coverArtist",
  // producers
  "editor",
  "edits",
  "editing",
];
Object.freeze(HEAD_ROLES);
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

function compareByLastName(a, b) {
  const aLast = a.name.split(" ").pop();
  const bLast = b.name.split(" ").pop();
  return aLast.localeCompare(bLast);
}

function renameKey(obj, oldKey, newKey) {
  const desc = Object.getOwnPropertyDescriptor(obj, oldKey);
  if (!desc) {
    return;
  }
  Object.defineProperty(obj, newKey, desc);
  delete obj[oldKey];
}

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  getters: {
    _mappedCredits(state) {
      const credits = {};
      if (!state?.md?.credits) {
        return credits;
      }

      // Convert credits into a role based map
      for (const { role, person } of state.md.credits) {
        if (!(role.name in credits)) {
          credits[role.name] = [];
        }
        credits[role.name].push(person);
      }

      // Sort persons by last name
      for (const [roleName, persons] of Object.entries(credits)) {
        credits[roleName] = persons.sort(compareByLastName);
      }

      return credits;
    },
    _sortedRoles(state) {
      // Sort the roles by special known order and then alphabetically.
      const roles = new Set(Object.keys(state._mappedCredits));
      const sortedRoles = [];
      for (const role of HEAD_ROLES) {
        if (roles.has(role)) {
          sortedRoles.push(role);
          roles.delete(role);
        }
      }
      const tailRoles = [...roles].sort();
      return [...sortedRoles, ...tailRoles];
    },
    credits(state) {
      return this.mapTag(state._mappedCredits, state._sortedRoles);
    },
    identifiers(state) {
      const identifiers = [];
      if (!state.md?.identifiers) {
        return identifiers;
      }
      for (const identifier of state.md.identifiers) {
        const parts = identifier.name.split(":");
        const idType = parts[0];
        const code = parts[1];
        const finalTitle = useBrowserStore().identifierTypeTitle(idType);
        let name = "";
        if (finalTitle && finalTitle !== "None") {
          name += finalTitle + ":";
        }
        name += code;

        const item = {
          pk: identifier.pk,
          url: identifier.url,
          name,
        };
        identifiers.push(item);
      }
      return identifiers;
    },
    tags(state) {
      const tags = state.mapTag(state.md, TAGS);

      renameKey(tags, "Story Arc Numbers", "Story Arcs");
      if (state.identifiers?.length) {
        tags["Identifiers"] = {
          filter: "identifiers",
          tags: this.identifiers,
        };
      }

      for (const [tagName, tagObj] of Object.entries(tags)) {
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
    mapTag(tagSource, keys) {
      const tagMap = {};

      for (const key of keys) {
        const tags = tagSource[key];
        if (!tags?.length) {
          continue;
        }
        const tagName = capitalCase(key);
        tagMap[tagName] = { filter: key, tags };
      }
      return tagMap;
    },
  },
});
