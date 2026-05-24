<template>
  <div id="editPanel">
    <div id="editToolbar">
      <v-btn
        color="primary"
        variant="flat"
        :loading="saving"
        :disabled="!hasChanges"
        @click="save"
      >
        Save Tags
      </v-btn>
      <v-btn variant="text" @click="$emit('cancel')"> Cancel </v-btn>
    </div>
    <v-select
      v-model="selectedFormats"
      :items="formatChoices"
      label="Metadata Formats"
      density="compact"
      hide-details
      multiple
      chips
      class="formatSelect"
    />

    <!-- Groups -->
    <section class="mdSection">
      <div class="inlineRow">
        <v-text-field
          v-model="patch.publisher"
          label="Publisher"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('publisher')"
        />
        <v-text-field
          v-model="patch.imprint"
          label="Imprint"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('imprint')"
        />
      </div>
      <div class="inlineRow">
        <v-text-field
          v-model="patch.series"
          label="Series"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('series')"
        />
        <v-text-field
          v-model="patch.volume"
          label="Volume"
          type="number"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('volume')"
        />
        <v-text-field
          v-model="patch.volume_issue_count"
          label="Issue Count"
          type="number"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('volume_issue_count')"
        />
      </div>
    </section>

    <!-- Summary / Review -->
    <section class="mdSection">
      <v-textarea
        v-model="patch.summary"
        label="Summary"
        rows="3"
        auto-grow
        hide-details
        density="compact"
        :disabled="isFieldDisabled('summary')"
      />
      <v-textarea
        v-model="patch.review"
        label="Review"
        rows="2"
        auto-grow
        hide-details
        density="compact"
        :disabled="isFieldDisabled('review')"
      />
    </section>

    <!-- Credits -->
    <v-table class="mdSection">
      <tbody>
        <tr v-for="role in creditRoles" :key="role">
          <td class="key">{{ role }}</td>
          <td>
            <v-combobox
              v-model="creditsByRole[role]"
              multiple
              chips
              closable-chips
              hide-details
              density="compact"
              :disabled="isFieldDisabled('credits')"
            />
          </td>
        </tr>
        <tr>
          <td>
            <v-select
              v-if="availableRoles.length > 0"
              v-model="selectedNewRole"
              :items="availableRoles"
              label="Add role..."
              density="compact"
              hide-details
              :disabled="isFieldDisabled('credits')"
              @update:model-value="addRole"
            />
          </td>
          <td class="clearCol">
            <v-btn
              v-if="creditRoles.length"
              variant="text"
              size="x-small"
              @click="clearField('credits')"
            >
              Clear All
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>

    <!-- Technical -->
    <section class="mdSection">
      <div class="thirdRow">
        <v-select
          v-model="patch.reading_direction"
          :items="readingDirectionItems"
          label="Reading Direction"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('reading_direction')"
          @click:clear="clearedFields.add('reading_direction')"
        />
        <v-select
          v-model="patch.original_format"
          :items="originalFormatChoices"
          label="Original Format"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('original_format')"
          @click:clear="clearedFields.add('original_format')"
        />
        <v-checkbox
          v-model="patch.monochrome"
          label="Monochrome"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('monochrome')"
        />
      </div>
      <div class="inlineRow">
        <v-select
          v-model="patch.country"
          :items="countryChoices"
          label="Country"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('country')"
          @click:clear="clearedFields.add('country')"
        />
        <v-select
          v-model="patch.language"
          :items="languageChoices"
          label="Language"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('language')"
          @click:clear="clearedFields.add('language')"
        />
        <v-select
          v-model="patch.age_rating"
          :items="ageRatingChoices"
          label="Age Rating"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('age_rating')"
          @click:clear="clearedFields.add('age_rating')"
        />
      </div>
      <div class="inlineRow">
        <v-select
          v-model="patch.main_character"
          :items="patch.characters"
          label="Main Character"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('protagonist')"
        />
        <v-select
          v-model="patch.main_team"
          :items="patch.teams"
          label="Main Team"
          hide-details
          density="compact"
          clearable
          :disabled="isFieldDisabled('protagonist')"
        />
      </div>
      <div class="readOnlyRow">
        <span v-if="md?.createdAt" class="readOnlyField">
          <span class="readOnlyLabel">Created at</span>
          {{ formatDateTime(md.createdAt) }}
        </span>
        <span v-if="md?.updatedAt" class="readOnlyField">
          <span class="readOnlyLabel">Updated at</span>
          {{ formatDateTime(md.updatedAt) }}
        </span>
        <span v-if="totalSize" class="readOnlyField">
          <span class="readOnlyLabel">{{ sizeLabel }}</span>
          {{ totalSize }}
        </span>
        <span v-if="fileType" class="readOnlyField">
          <span class="readOnlyLabel">File Type</span>
          {{ fileType }}
        </span>
      </div>
      <div v-if="md?.path" class="readOnlyRow">
        <span class="readOnlyField">
          <span class="readOnlyLabel">Path</span>
          {{ md.path }}
        </span>
      </div>
    </section>

    <!-- Tags -->
    <v-table class="mdSection">
      <tbody>
        <tr v-for="tagKey in tagKeys" :key="tagKey">
          <td class="key">
            {{ tagLabel(tagKey) }}
            <v-btn
              v-if="patch[tagKey]?.length"
              icon
              size="x-small"
              variant="text"
              @click="clearField(tagKey)"
            >
              &times;
            </v-btn>
          </td>
          <td>
            <v-combobox
              v-model="patch[tagKey]"
              multiple
              chips
              closable-chips
              hide-details
              density="compact"
              :disabled="isFieldDisabled(tagKey)"
            />
          </td>
        </tr>
        <tr>
          <td class="key">
            Story Arcs
            <v-btn
              v-if="storyArcNames.length"
              icon
              size="x-small"
              variant="text"
              @click="clearField('story_arcs')"
            >
              &times;
            </v-btn>
          </td>
          <td>
            <v-combobox
              v-model="storyArcNames"
              multiple
              chips
              closable-chips
              hide-details
              density="compact"
              :disabled="isFieldDisabled('story_arcs')"
            />
          </td>
        </tr>
      </tbody>
    </v-table>

    <!-- Universes -->
    <v-table class="mdSection">
      <tbody>
        <tr v-for="(u, i) in universes" :key="i">
          <td>
            <v-combobox
              v-model="universes[i].name"
              label="Universe"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('universes')"
            />
          </td>
          <td>
            <v-text-field
              v-model="universes[i].designation"
              label="Designation"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('universes')"
            />
          </td>
          <td class="removeCol">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="universes.splice(i, 1)"
            >
              &times;
            </v-btn>
          </td>
        </tr>
        <tr>
          <td colspan="2">
            <v-btn
              variant="text"
              size="small"
              :disabled="isFieldDisabled('universes')"
              @click="universes.push({ name: '', designation: '' })"
            >
              + Add Universe
            </v-btn>
          </td>
          <td class="clearCol">
            <v-btn
              v-if="universes.length"
              variant="text"
              size="x-small"
              @click="clearField('universes')"
            >
              Clear All
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>

    <!-- Identifiers -->
    <v-table class="mdSection">
      <tbody>
        <tr v-for="(id, i) in identifiers" :key="i">
          <td>
            <v-select
              v-model="identifiers[i].source"
              :items="identifierSourceChoices"
              label="Source"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td>
            <v-select
              v-model="identifiers[i].id_type"
              :items="identifierTypeChoices"
              label="Type"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td>
            <v-text-field
              v-model="identifiers[i].key"
              label="Key"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td class="removeCol">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="identifiers.splice(i, 1)"
            >
              &times;
            </v-btn>
          </td>
        </tr>
        <tr>
          <td colspan="3">
            <v-btn
              variant="text"
              size="small"
              :disabled="isFieldDisabled('identifiers')"
              @click="
                identifiers.push({ source: '', id_type: 'comic', key: '' })
              "
            >
              + Add Identifier
            </v-btn>
          </td>
          <td class="clearCol">
            <v-btn
              v-if="identifiers.length"
              variant="text"
              size="x-small"
              @click="clearField('identifiers')"
            >
              Clear All
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>

    <!-- Notes / Tagger / Scan -->
    <section class="mdSection">
      <v-textarea
        v-model="patch.notes"
        label="Notes"
        rows="2"
        auto-grow
        hide-details
        density="compact"
        :disabled="isFieldDisabled('notes')"
      />
      <div class="inlineRow">
        <v-text-field
          v-model="patch.tagger"
          label="Tagger"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('tagger')"
        />
        <v-text-field
          v-model="patch.scan_info"
          label="Scan Info"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('scan_info')"
        />
      </div>
    </section>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import { capitalCase } from "text-case";
import prettyBytes from "pretty-bytes";

import { HTTP } from "@/api/v3/base";
import AGE_RATINGS from "@/choices/age-ratings.json";
import COUNTRIES from "@/choices/countries.json";
import FORMAT_FIELD_SUPPORT from "@/choices/format-field-support.json";
import IDENTIFIER_SOURCES from "@/choices/identifier-sources.json";
import IDENTIFIER_TYPES from "@/choices/identifier-types.json";

const FORMAT_CHOICES = [
  { title: "MetronInfo", value: "METRON_INFO" },
  { title: "ComicInfo", value: "COMIC_INFO" },
];
import LANGUAGES from "@/choices/languages.json";
import ORIGINAL_FORMATS from "@/choices/original-formats.json";
import { getDateTime } from "@/datetime";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useMetadataStore } from "@/stores/metadata";

const TAG_KEYS = [
  "genres",
  "characters",
  "teams",
  "locations",
  "series_groups",
  "stories",
  "tags",
];

const ALL_ROLES = Object.freeze([
  "Writer",
  "Author",
  "Plotter",
  "Plot",
  "Script",
  "Scripter",
  "Story",
  "Interviewer",
  "Translator",
  "Artist",
  "Penciller",
  "Breakdowns",
  "Pencils",
  "Illustrator",
  "Layouts",
  "Inker",
  "Finishes",
  "Inks",
  "Embellisher",
  "Ink Assists",
  "Colorist",
  "Colorer",
  "Colourer",
  "Colors",
  "Colours",
  "Color Designer",
  "Color Flats",
  "Color Separations",
  "Designer",
  "Digital Art Technician",
  "Gray Tone",
  "Letterer",
  "Cover",
  "Covers",
  "Cover Artist",
  "Editor",
  "Edits",
  "Editing",
]);

export default {
  name: "EditPanel",
  props: {
    book: {
      type: Object,
      required: true,
    },
  },
  emits: ["cancel", "saved"],
  data() {
    return {
      formatChoices: FORMAT_CHOICES,
      originalFormatChoices: ORIGINAL_FORMATS,
      selectedFormats: ["COMIC_INFO"],
      countryChoices: COUNTRIES,
      languageChoices: LANGUAGES,
      ageRatingChoices: AGE_RATINGS,
      identifierSourceChoices: IDENTIFIER_SOURCES,
      identifierTypeChoices: IDENTIFIER_TYPES,
      tagKeys: TAG_KEYS,
      saving: false,
      clearedFields: new Set(),
      selectedNewRole: null,
      creditsByRole: {},
      storyArcNames: [],
      universes: [],
      identifiers: [],
      patch: {
        publisher: "",
        imprint: "",
        series: "",
        volume: "",
        volume_issue_count: "",
        summary: "",
        review: "",
        notes: "",
        tagger: "",
        scan_info: "",
        reading_direction: null,
        original_format: null,
        monochrome: false,
        country: null,
        language: null,
        age_rating: null,
        main_character: "",
        main_team: "",
        genres: [],
        characters: [],
        teams: [],
        locations: [],
        series_groups: [],
        stories: [],
        tags: [],
      },
    };
  },
  computed: {
    ...mapState(useMetadataStore, ["md"]),
    ...mapState(useAdminStore, ["taggingDefaults"]),
    ...mapState(useBrowserStore, {
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
    }),
    readingDirectionItems() {
      if (!this.readingDirectionTitles) return [];
      return Object.entries(this.readingDirectionTitles).map(
        ([value, title]) => ({ title, value }),
      );
    },
    enabledFormats() {
      return this.selectedFormats.length > 0
        ? this.selectedFormats
        : ["COMIC_INFO"];
    },
    supportedFields() {
      const supported = new Set();
      for (const fmt of this.enabledFormats) {
        const fields = FORMAT_FIELD_SUPPORT[fmt];
        if (fields) {
          for (const f of fields) supported.add(f);
        }
      }
      return supported;
    },
    creditRoles() {
      return Object.keys(this.creditsByRole);
    },
    availableRoles() {
      const existing = new Set(this.creditRoles);
      return ALL_ROLES.filter((r) => !existing.has(r));
    },
    totalSize() {
      return this.md?.size > 0 ? prettyBytes(this.md.size) : "";
    },
    sizeLabel() {
      return this.md?.group === "c" ? "Size" : "Total Size";
    },
    fileType() {
      return this.md?.fileType || "";
    },
    hasChanges() {
      if (this.clearedFields.size > 0) return true;
      for (const [k, v] of Object.entries(this.patch)) {
        if (k === "monochrome") continue;
        if (k === "reading_direction" || k === "original_format" || k === "country" || k === "language" || k === "age_rating") {
          if (v) return true;
          continue;
        }
        if (Array.isArray(v) ? v.length > 0 : Boolean(v)) return true;
      }
      if (this.storyArcNames.length > 0) return true;
      if (this.universes.length > 0) return true;
      if (this.identifiers.length > 0) return true;
      for (const persons of Object.values(this.creditsByRole)) {
        if (persons.length > 0) return true;
      }
      return false;
    },
  },
  mounted() {
    this.loadTaggingDefaults();
    if (this.taggingDefaults?.defaultFormats?.length) {
      this.selectedFormats = [...this.taggingDefaults.defaultFormats];
    }
    this.initFromMetadata();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTaggingDefaults"]),
    isFieldDisabled(field) {
      return !this.supportedFields.has(field);
    },
    tagLabel(key) {
      if (key === "series_groups") return "Series Groups";
      return capitalCase(key);
    },
    clearField(field) {
      this.clearedFields.add(field);
      if (field in this.patch) {
        const val = this.patch[field];
        if (Array.isArray(val)) {
          this.patch[field] = [];
        } else if (typeof val === "boolean") {
          this.patch[field] = false;
        } else {
          this.patch[field] = "";
        }
      }
      if (field === "credits") {
        this.creditsByRole = {};
      } else if (field === "story_arcs") {
        this.storyArcNames = [];
      } else if (field === "universes") {
        this.universes = [];
      } else if (field === "identifiers") {
        this.identifiers = [];
      }
    },
    addRole(role) {
      if (role && !(role in this.creditsByRole)) {
        this.creditsByRole[role] = [];
      }
      this.selectedNewRole = null;
    },
    formatDateTime(ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
    initFromMetadata() {
      if (!this.md) return;

      // Text fields
      this.patch.summary = this.md.summary || "";
      this.patch.review = this.md.review || "";
      this.patch.notes = this.md.notes || "";
      this.patch.tagger = this.md.tagger?.name || "";
      this.patch.scan_info = this.md.scanInfo?.name || "";

      // Groups
      this.patch.publisher = this.md.publisherList?.[0]?.name || "";
      this.patch.imprint = this.md.imprintList?.[0]?.name || "";
      this.patch.series = this.md.seriesList?.[0]?.name || "";
      this.patch.volume = this.md.volumeList?.[0]?.name || "";
      this.patch.volume_issue_count = this.md.volumeIssueCount || "";

      // Tags
      for (const key of TAG_KEYS) {
        const camelKey = key.replace(/_(\w)/g, (_, c) => c.toUpperCase());
        const tags = this.md[camelKey];
        if (tags?.length) {
          this.patch[key] = tags.map((t) => t.name);
        }
      }

      // Story arcs
      if (this.md.storyArcNumbers?.length) {
        this.storyArcNames = this.md.storyArcNumbers.map((a) => a.name);
      }

      // Credits — group by role
      if (this.md.credits?.length) {
        const grouped = {};
        for (const c of this.md.credits) {
          const role = c.role?.name || "Other";
          if (!(role in grouped)) {
            grouped[role] = [];
          }
          grouped[role].push(c.person?.name || "");
        }
        this.creditsByRole = grouped;
      }

      // Universes — name + optional designation
      if (this.md.universes?.length) {
        this.universes = this.md.universes.map((u) => ({
          name: u.name,
          designation: u.designation || "",
        }));
      }

      /* Identifiers — name property format: "source::id_type:key" */
      if (this.md.identifiers?.length) {
        this.identifiers = this.md.identifiers.map((id) => {
          const rawKey = id.key || "";
          const name = id.name || "";
          const prefix =
            rawKey && name.endsWith(`:${rawKey}`)
              ? name.slice(0, -(rawKey.length + 1))
              : name;
          const parts = prefix.split(":").filter(Boolean);
          return {
            source: parts.length > 1 ? parts[0] : "",
            id_type: parts.length > 1 ? parts[1] : parts[0] || "",
            key: rawKey,
          };
        });
      }

      // Technical
      this.patch.reading_direction = this.md.readingDirection || null;
      this.patch.original_format = this.md.originalFormat?.name || null;
      this.patch.monochrome = Boolean(this.md.monochrome);
      this.patch.country = this.md.country?.name || null;
      this.patch.language = this.md.language?.name || null;
      this.patch.age_rating = this.md.ageRating?.name || null;
      this.patch.main_character = this.md.mainCharacter?.name || "";
      this.patch.main_team = this.md.mainTeam?.name || "";
    },
    buildPatch() {
      const cbPatch = {};
      const cleared = this.clearedFields;

      // Simple strings — include if has value OR explicitly cleared
      for (const key of [
        "summary",
        "review",
        "notes",
        "tagger",
        "scan_info",
      ]) {
        if (this.patch[key]) {
          cbPatch[key] = this.patch[key];
        } else if (cleared.has(key)) {
          cbPatch[key] = "";
        }
      }

      // Tag arrays
      for (const key of TAG_KEYS) {
        if (this.patch[key].length > 0) {
          cbPatch[key] = this.patch[key];
        } else if (cleared.has(key)) {
          cbPatch[key] = {};
        }
      }

      // Groups → SimpleNamedNestedField
      for (const key of ["publisher", "imprint", "series"]) {
        if (this.patch[key]) {
          cbPatch[key] = { name: this.patch[key] };
        } else if (cleared.has(key)) {
          cbPatch[key] = { name: "" };
        }
      }
      if (this.patch.volume) {
        const num = parseInt(this.patch.volume, 10);
        if (!isNaN(num)) {
          const vol = { number: num };
          if (this.patch.volume_issue_count) {
            const ic = parseInt(this.patch.volume_issue_count, 10);
            if (!isNaN(ic)) vol.issue_count = ic;
          }
          cbPatch.volume = vol;
        }
      }

      // Story arcs
      if (this.storyArcNames.length > 0) {
        const arcs = {};
        for (const name of this.storyArcNames) {
          arcs[name] = {};
        }
        cbPatch.arcs = arcs;
      } else if (cleared.has("story_arcs")) {
        cbPatch.arcs = {};
      }

      // Credits
      const credits = {};
      for (const [role, persons] of Object.entries(this.creditsByRole)) {
        for (const person of persons) {
          if (!person) continue;
          if (!(person in credits)) {
            credits[person] = { roles: {} };
          }
          if (role) {
            credits[person].roles[role] = {};
          }
        }
      }
      if (Object.keys(credits).length) {
        cbPatch.credits = credits;
      } else if (cleared.has("credits")) {
        cbPatch.credits = {};
      }

      // Universes
      if (this.universes.length > 0) {
        const univs = {};
        for (const u of this.universes) {
          if (u.name) {
            univs[u.name] = u.designation
              ? { designation: u.designation }
              : {};
          }
        }
        if (Object.keys(univs).length) cbPatch.universes = univs;
      } else if (cleared.has("universes")) {
        cbPatch.universes = {};
      }

      // Identifiers
      if (this.identifiers.length > 0) {
        const ids = {};
        for (const id of this.identifiers) {
          if (id.source && id.key) {
            const fullKey = id.id_type ? `${id.id_type}:${id.key}` : id.key;
            ids[id.source] = { key: fullKey, url: "" };
          }
        }
        if (Object.keys(ids).length) cbPatch.identifiers = ids;
      } else if (cleared.has("identifiers")) {
        cbPatch.identifiers = {};
      }

      // Technical — select fields: value or cleared
      for (const key of [
        "reading_direction",
        "original_format",
        "country",
        "language",
        "age_rating",
      ]) {
        if (this.patch[key]) {
          cbPatch[key] = this.patch[key];
        } else if (cleared.has(key)) {
          cbPatch[key] = "";
        }
      }
      if (this.patch.monochrome) {
        cbPatch.monochrome = this.patch.monochrome;
      }

      // Protagonist
      const protagonist = this.patch.main_character || this.patch.main_team;
      if (protagonist) {
        cbPatch.protagonist = protagonist;
      } else if (cleared.has("protagonist")) {
        cbPatch.protagonist = "";
      }

      return cbPatch;
    },
    async save() {
      this.saving = true;
      const pks = this.book.ids || [this.book.pk];
      const formats = this.enabledFormats;
      const cbPatch = this.buildPatch();

      try {
        await HTTP.post("/admin/tagwrite", {
          group: this.book.group,
          pks: pks.map(String),
          patch: cbPatch,
          mode: "update",
          formats,
        });
        useCommonStore().setSuccess("Tag write queued.");
        this.$emit("saved");
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "../table";

#editPanel {
  padding-bottom: 20px;
}

#editToolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 1;
  background-color: rgb(var(--v-theme-surface));
}

.formatSelect {
  margin-top: 8px;
}

.mdSection {
  margin-top: 25px;
  background-color: rgb(var(--v-theme-surface));
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inlineRow {
  display: flex;
  gap: 8px;
}

.inlineRow > * {
  flex: 1;
}

.thirdRow {
  display: flex;
  gap: 8px;
}

.thirdRow > * {
  flex: 1;
}

.clearCol {
  text-align: right;
  width: 1%;
  white-space: nowrap;
}

.removeCol {
  width: 1%;
  white-space: nowrap;
}

.readOnlyRow {
  display: flex;
  gap: 16px;
  padding: 10px 0 0;
}

.readOnlyField {
  color: rgb(var(--v-theme-textSecondary));
  font-size: 0.85em;
}

.readOnlyLabel {
  font-size: 12px;
  display: block;
  color: rgb(var(--v-theme-textDisabled));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #editPanel {
    font-size: 12px;
  }

  .key {
    font-size: small;
  }
}
</style>
