<template>
  <v-dialog
    v-model="dialog"
    content-class="browserSearchHelp"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <template #activator="{ props }">
      <DrawerItem
        v-bind="props"
        :prepend-icon="mdiArchiveSearchOutline"
        title="Search Help"
      />
    </template>
    <div id="searchHelp">
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        size="x-large"
        @click="dialog = false"
      />
      <h1>Search Help</h1>
      <div id="fieldTableContainer">
        <h2>Search Fields</h2>
        <v-table id="fieldTable" class="highlight-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Type</th>
              <th>Aliases</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in FIELD_ROWS" :key="row[0]">
              <td>{{ row[0] }}</td>
              <td>{{ row[1] }}</td>
              <td class="aliasCol">
                {{ row[2] || "" }}
              </td>
            </tr>
          </tbody>
        </v-table>
      </div>
      <div id="textContainer">
        <h2>Search Syntax</h2>
        <p>
          Codex allows two different kinds of searching from the search bar.
          Full Text Search and Field Search. For full text search just enter
          some terms in the search bar. They will be added to the filters
          selected with the "filter by" menu.
        </p>
        <p>Searching in Codex is always case insensitive.</p>
        <h2>Full Text Search</h2>
        <p>
          Full text search searches all the metadata of a comic as one document.
        </p>
        <h3>Boolean Operators</h3>
        <p>
          Codex allows the <code>AND</code>, <code>OR</code>, and
          <code>NOT</code> operators between search terms. By default terms are
          concatenated with the <code>AND</code> operator. For instance:
          <code> frodo sam galadriel </code>
          is the same as <code>frodo AND sam AND galadriel</code>.

          <code> frodo OR pippin NOT merry</code> searches for comics with
          metadata that reference Frodo or Pippin but not Merry. Parenthesis may
          be used to group boolean operators.
        </p>
        <h3>Prefix Operators</h3>
        <p>
          search tokens suffixed with a <code>*</code> will look for text with
          the given prefix. For example <code>tev*</code> should match if the
          string "Tevildo" occurs anywhere in the comic metadata.
        </p>
        <h2>Field Search Syntax</h2>
        <p>
          Similar to Codex's filter selector menu, you may query individual
          comic fields in the database, but for more columns and with more
          powerful operators than the exact match offered by the filter menu. A
          field search looks like: <code>field:expression</code>.
        </p>
        <p>
          The field syntax is parsed and removed from the search query
          <em>before</em> parsing the remaining search string as a Full Text
          Search. Thus field query tokens are applied to the search but ignored
          by Full Text Search Boolean Operators.
        </p>
        <h3>Simple Values as the Expression</h3>
        <p>
          Simple values entered for the expression match exactly for numeric,
          datetime and boolean fields. However for text fields the field is
          searched for any match of the entered value.
        </p>
        <h3>Leading Operators</h3>
        <p>
          Field Search has it's own operators that offer more powerful queries.
          For text, numeric, boolean and datetime fields may be applied at the
          beginning of the expression
          <code>&gt;</code
          >,<code>&gt;=</code>,<code>&lt;</code>,<code>&lt;=</code>,
          <code>!</code>. The <code>!</code> character indicates excluding the
          following value. And the range syntax <code>..</code> accepts two
          values. For instance:
        </p>
        <table>
          <tbody>
            <tr>
              <td><code>pages:>30</code></td>
              <td>comics with more than 30 pages</td>
            </tr>
            <tr>
              <td><code>author:!frodo</code></td>
              <td>comics not written by Frodo</td>
            </tr>
            <tr>
              <td><code>year:1066..1215</code></td>
              <td>comics published between the year 1066 and 1215.</td>
            </tr>
          </tbody>
        </table>
        <h3>Text Operators</h3>
        <p>
          Field search on text fields may be narrowed using the
          <code>*</code> operator:
        </p>
        <table>
          <tbody>
            <tr>
              <td><code>characters:Ar*</code></td>
              <td>
                characters that start with "Ar", like "Aragorn" and "Arwen"
              </td>
            </tr>
            <tr>
              <td><code>characters:*ond</code></td>
              <td>characters that end with "ond", like "Elrond"</td>
            </tr>
            <tr>
              <td><code>series:sil*ion</code></td>
              <td>series such as Silmarillion</td>
            </tr>
          </tbody>
        </table>
        <p>
          Leading operators on text fields will perform much less efficient
          lookups than <code>field:bare-words</code> and
          <code>field:prefix*</code> operators. The latter is able to leverage
          the fast full text indexing.
        </p>
        <h3>Dates and DateTimes</h3>
        <p>
          Codex parses Dates and DateTime values liberally. Read documentation
          for what formats and natural language phrases are accepted. If the
          format you try fails, the <code>YYYY-MM-DD</code> and
          <code>YYYY-MM-DD:HH:mm:SS</code> formats are reliable. Many quoted
          english phrases also work, for instance:
          <code>created_at:"3 days ago".."today"</code>
        </p>
        <h3>Single Quote complex field Queries</h3>
        <p>
          Use quotes to tell Codex that a complex or natural language phrase
          should be applied to a specific field
        </p>
        <code> created:'this year' </code>
        <h3>Size Byte Multipliers</h3>
        <p>
          The size field can make use of convenient byte multiplier suffixes
          like
          <code>kb</code> and <code>mb</code> as well as binary suffixes like
          <code>gib</code> and <code>tib</code>. For instance
          <code>size:>10mb</code>
        </p>
        <h3>Multiple Values</h3>
        <p>
          Fields may have multiple expressions that all match against the same
          field:
          <code>field:value1,!value2,>=value3</code>
          If separated by a comma <code>,</code> the terms are ANDed together
          and a row must match all the expressions. If separated by a pipe
          <code>|</code> they are ORed together row will match if any of the
          expressions match.
        </p>
      </div>
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        size="x-large"
        @click="dialog = false"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiArchiveSearchOutline, mdiOpenInNew } from "@mdi/js";

import CloseButton from "@/components/close-button.vue";
import DrawerItem from "@/components/drawer-item.vue";

const FIELD_ROWS = [
  ["characters", "CSV", "category"],
  ["community_rating", "Decimal", "communityrating"],
  ["contributor", "CSV", "author, creator, credit, person, people"],
  ["country", "String"],
  ["created_at", "DateTime", "created"],
  ["critical_rating", "Decimal", "criticalrating"],
  ["day", "Integer"],
  ["date", "Date"],
  ["decade", "Integer"],
  ["file_type", "String", "filetype, type"],
  ["genres", "CSV", "genre"],
  ["identifiers", "CSV", "id, nss"],
  ["identifier_types", "CSV", "id_type, idtype, nid"],
  ["imprint", "String"],
  ["issue", "String", "(Combined issue_number and issue_suffix)"],
  ["issue_number", "Decimal", "number"],
  ["issue_suffix", "String"],
  ["language", "String"],
  ["location", "CSV", "location"],
  ["maturity_rating", "String"],
  ["monochrome", "String", "blackandwhite"],
  ["month", "Integer"],
  ["reading_direction", "String", "direction"],
  ["name", "String", "title"],
  ["notes", "String"],
  ["original_format", "String", "format, orginalformat"],
  ["path", "String", "filename, folder, folders"],
  ["page_count", "Integer", "pages, pagecount"],
  ["publisher", "String"],
  ["reading_direction", "String", "direction"],
  ["review", "String"],
  ["scan_info", "String", "scan, scaninfo"],
  ["series", "String"],
  ["series_groups", "CSV", "seriesgroups"],
  ["size", "Integer"],
  ["stories", "CSV", "story"],
  ["story_arcs", "CSV", "storyarcs"],
  ["summary", "String", "comments, description"],
  ["tags", "CSV", "tag"],
  ["tagger", "String"],
  ["teams", "CSV", "team"],
  ["updated_at", "Date", "updated"],
  ["volume", "String"],
  ["web", "String"],
  ["year", "Integer"],
];

export default {
  name: "SearchHelp",
  components: { CloseButton, DrawerItem },
  data() {
    return {
      mdiOpenInNew,
      mdiArchiveSearchOutline,
      dialog: false,
      FIELD_ROWS,
    };
  },
};
</script>

<style scoped lang="scss">
@import "../../anchors.scss";

:deep(.browserSearchHelp) {
  overflow-y: auto !important;
}

#searchHelp {
  max-width: 850px;
  padding: 20px;
  padding-left: 20px;
  padding-right: 20px;
  margin: auto;
  color: rgb(var(--v-theme-textSecondary));
}

h1,
h2,
h3 {
  margin-top: 0.5em;
  color: rgb(var(--v-theme-textHeader));
}

h1 {
  padding-bottom: 1em;
}

.closeButton {
  float: right;
}

#fieldTableContainer {
  float: left;
}

#fieldTable {
  width: fit-content;
  text-align: left;
  margin-bottom: 1em;
  margin-right: 2em;
  color: rgb(var(--v-theme-textSecondary));
}

#fieldTable th {
  font-size: larger;
  font-weight: bold;
  color: rgb(var(--v-theme-textHeader));
}

#fieldTable th,
#fieldTable td {
  padding: 5px;
}

#fieldTable .aliasCol {
  max-width: 10em;
}

code {
  width: fit-content;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textHeader)) !important;
}
</style>
