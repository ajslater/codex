import { defineStore } from "pinia";
import { capitalCase } from "text-case";

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
  // identifiers
  "teams",
  "locations",
  "seriesGroups",
  "stories",
  "storyArcNumbers",
  "tags",
  "universes",
];
Object.freeze(TAGS);
const MAIN_TAGS = new Set(["Characters", "Teams"]);
Object.freeze(MAIN_TAGS);

function compareByLastName(a, b) {
  const aLast = a.name.split(" ").pop();
  const bLast = b.name.split(" ").pop();
  return aLast.localeCompare(bLast);
}

export const useMetadataStore = defineStore("metadata", {
  state: () => ({
    md: undefined,
  }),
  getters: {
    roleMap(state) {
      const rm = {};
      for (const { role } of state.md.credits) {
        const roleName = role?.name ? role.name : "Other";
        rm[roleName] = role;
      }
      return rm;
    },
    _mappedCredits(state) {
      const credits = {};
      if (!state?.md?.credits) {
        return credits;
      }

      // Convert credits into a role based map
      for (const { role, person } of state.md.credits) {
        const roleName = role?.name ? role.name : "Other";
        if (!(roleName in credits)) {
          credits[roleName] = [];
        }
        credits[roleName].push(person);
      }

      // Sort persons by last name
      for (const [roleName, persons] of Object.entries(credits)) {
        credits[roleName] = persons.sort(compareByLastName);
      }

      return credits;
    },
    _sortedRoles(state) {
      // Sort the roles by special known order and then alphabetically.
      const roles = Object.keys(state._mappedCredits);
      const lowercaseRoleMap = {};
      for (const originalRole of roles) {
        lowercaseRoleMap[originalRole.toLowerCase()] = originalRole;
      }

      const sortedRoles = [];
      for (const role of HEAD_ROLES) {
        const originalRole = lowercaseRoleMap[role];
        if (!originalRole) {
          continue;
        }
        sortedRoles.push(originalRole);
        delete lowercaseRoleMap[role];
        if (!Object.keys(lowercaseRoleMap).length) {
          break;
        }
      }
      roles.sort();
      sortedRoles.push(roles);
      return sortedRoles;
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
        const finalTitle = useBrowserStore().identifierSourceTitle(idType);
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
    mapTag(tagSource, keys) {
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

        tagMap[tagName] = { filter: key, tags: regularTags, mainTags };
      }
      return tagMap;
    },
    lazyImport({ group, ids }) {
      return API.getLazyImport({ group, pks: ids });
    },
  },
});
