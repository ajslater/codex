<template>
  <v-dialog
    v-model="dialog"
    fullscreen
    transition="dialog-bottom-transition"
    content-class="browserSearchHelp"
  >
    <template #activator="{ props }">
      <v-list-item ripple v-bind="props">
        <v-list-item-title
          ><v-icon>{{ mdiArchiveSearchOutline }}</v-icon> Search Syntax Help
        </v-list-item-title>
      </v-list-item>
    </template>
    <div id="searchHelp">
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        x-large
        @click="dialog = false"
      />
      <h1>Search Syntax Help</h1>
      <div id="fieldTableContainer">
        <h2>Search Fields</h2>
        <table id="fieldTable" class="highlight-table">
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
              <td>{{ row[2] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div id="textContainer">
        <h2>Xapian Query Parser</h2>
        <p>
          Codex uses the Xapian search backend to execute your text search
          queries. Xapian operates much like other familiar search engines. As
          such, I document only some special features on this page. I encourage
          users looking to understand its full power to read the
          <a href="https://xapian.org/docs/queryparser.html" target="_blank"
            >Xapian Query Parser Syntax documentation
            <v-icon small>{{ mdiOpenInNew }}</v-icon></a
          >.
        </p>

        <h2>Searching Fields</h2>
        <p>
          Like Codex's filter selector menu, but more powerful, you may search
          on individual comic metadata fields. using a search token like
          <code>field:value</code>.
        </p>
        <h3>Dates and DateTimes</h3>
        <p>
          Codex parses Dates and DateTime values liberally. If the format you
          enter fails, the
          <a href="https://en.wikipedia.org/wiki/ISO_8601" target="_blank"
            >ISO 8601 format<v-icon small>{{ mdiOpenInNew }}</v-icon></a
          >
          is reliable.
        </p>
        <h3>Size Byte Multipliers</h3>
        <p>
          The size field can make use of convenient byte multiplier suffixes
          like
          <code>kb</code> and <code>mb</code> as well as binary suffixes like
          <code>gib</code> and <code>tib</code>.
        </p>
        <h3>Ranges of Fields</h3>
        <p>
          Codex uses two dots <code>..</code> to delineate a range search in a
          field value. If you leave out the upper or lower bound, the wildcard
          <code>*</code> will tacitily take it's place. Range tokens look like
          <code>field:lower..upper</code>
          Be careful your range search doesn't contain three or more dots. This
          will cause codex to discard the upper bound value.
        </p>

        <h3>Multi Value Field</h3>
        <p>
          Fields marked type <code>CSV</code> may contain comma separated
          values. This filters by all the supplied values. Multi Value tokens
          look like:
          <code>field:term1,term2,term3</code>
        </p>

        <h2>Example Search</h2>
        <p>
          This example search is more convoluted than most searches but uses
          many features for demonstration:
        </p>
        <code>
          Holmes AND Tesla date:1999-1-2.. size:10mib..1gb Gadzooks NEAR
          "Captain Nemo" -Quartermain
        </code>
        <p style="margin-top: 1em">
          Search for comics that contain Holmes and Tesla published after the
          second day of 1999 that are between 10 Mebibytes and 10 Gigabytes that
          also contain the word "Gadzooks" near the phrase "Captain Nemo" but do
          not contain the word "Quartermain".
        </p>
        <h2>Group and Sorting Behavior</h2>
        <p>
          If the search field is empty and then you supply a search query for
          the first time, Codex navigates you to the to All Issues view and your
          sets your Sorted By selection to Search Score. If you prefer a
          different view you may change the group and sort selections after your
          you make your first search.
        </p>

        <h2>Filter Behavior</h2>
        <p>
          Codex applies <em>both</em> the Filter selection menu filters
          <em>and</em> the search query field filters to the search. Be sure to
          clear the filter selector or the search field if you prefer to apply
          only one of them.
        </p>
      </div>
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        x-large
        @click="dialog = false"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiArchiveSearchOutline, mdiOpenInNew } from "@mdi/js";

import CloseButton from "@/components/close-button.vue";

const FIELD_ROWS = [
  ["community_rating", "Decimal", ""],
  ["characters", "CSV", "character"],
  ["country", "String", ""],
  ["created_at", "DateTime", "created"],
  ["creators", "CSV", "creator"],
  ["critical_rating", "Decimal", ""],
  ["day", "Integer", ""],
  ["date", "Date", ""],
  ["decade", "Integer", ""],
  ["description", "String", ""],
  ["format", "String", ""],
  ["genres", "CSV", "genre"],
  ["imprint", "String", ""],
  ["in_progress", "Boolean", "reading"],
  ["issue", "Decimal", ""],
  ["language", "String", ""],
  ["locations", "CSV", "location"],
  ["maturity_rating", "String", ""],
  ["month", "Integer", ""],
  ["read_ltr", "Boolean", "ltr"],
  ["name", "String", "title"],
  ["notes", "String", ""],
  ["page_count", "Integer", ""],
  ["publisher", "String", ""],
  ["scan_info", "String", "scan"],
  ["series", "String", ""],
  ["series_groups", "CSV", "series_group"],
  ["size", "Integer", ""],
  ["story_arcs", "CSV", "story_arc"],
  ["summary", "String", ""],
  ["tags", "CSV", "tag"],
  ["teams", "CSV", "team"],
  ["updated_at", "Date", "updated"],
  ["unread", "Boolean", "finished, read"],
  ["volume", "String", ""],
  ["web", "String", ""],
  ["year", "Integer", ""],
];

export default {
  name: "SearchHelp",
  components: { CloseButton },
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
@import "../anchors.scss";
#searchHelp {
  max-width: 850px;
  padding: 20px;
  padding-left: 20px;
  padding-right: 20px;
  margin: auto;
  color: rgb(var(--v-theme-textDisabled));
}
h1,
h2,
h3 {
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
code {
  width: fit-content;
  color: rgb(var(--v-theme-textHeader)) !important;
}
</style>
