<template>
  <v-dialog
    v-model="dialog"
    content-class="browserSearchHelp"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <template #activator="{ props }">
      <v-list-item v-bind="props">
        <v-list-item-title
          ><v-icon>{{ mdiArchiveSearchOutline }}</v-icon
          >Search Syntax Help
        </v-list-item-title>
      </v-list-item>
    </template>
    <div id="searchHelp">
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        size="x-large"
        @click="dialog = false"
      />
      <h1>Search Syntax Help</h1>
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
              <td>{{ row[2] }}</td>
            </tr>
          </tbody>
        </v-table>
      </div>
      <div id="textContainer">
        <h2>Whoosh Query Parser</h2>
        <p>
          Codex uses the Whoosh search engine to execute your text search
          queries. Whoosh operates much like other familiar search engines. As
          such, only some special features are documented on this page. To
          understand its full power, users are encouraged to read the
          <a
            href="https://whoosh.readthedocs.io/en/latest/querylang.html"
            target="_blank"
            >Whoosh Query Language
            <v-icon size="small">{{ mdiOpenInNew }}</v-icon></a
          >
          documentation.
        </p>
        <h2>Operators</h2>
        Whoosh has the <code>and</code>, <code>or</code>, <code>not</code>,
        <code>andnot</code>, <code>andmaybe</code>, and
        <code>require</code> operators.
        <h2>Searching Fields</h2>
        <p>
          Like Codex's filter selector menu, but more powerful. You may search
          on individual comic metadata fields. using a search token like
          <code>field:value</code>.
        </p>
        <h3>Dates and DateTimes</h3>
        <p>
          Whoosh parses Dates and DateTime values liberally. Read
          <a
            href="https://whoosh.readthedocs.io/en/latest/dates.html#parsing-date-queries"
            target="_blank"
            >Whoosh Parsing Date Queries
            <v-icon size="small">{{ mdiOpenInNew }}</v-icon>
          </a>
          documentation for what formats and natural language phrases are
          accepted. If the format you try fails, the <code>YYYYMMDD</code> and
          <code>YYYMMDDHHmmSS</code> formats are reliable.
        </p>
        <h3>Single Quote complex field Queries</h3>
        <p>
          Use <em>single</em> quotes to tell Codex that a complex or natural
          language phrase should be applied to a specific field
        </p>
        <code> created:'this year' </code>
        <h3>Size Byte Multipliers</h3>
        <p>
          The size field can make use of convenient byte multiplier suffixes
          like
          <code>kb</code> and <code>mb</code> as well as binary suffixes like
          <code>gib</code> and <code>tib</code>.
        </p>
        <h3>Ranges of Fields</h3>
        <p>
          Whoosh uses brackets and the <em>uppercase</em>&ensp;<code>TO</code>
          operator to delineate a range search.
        </p>
        <code>updated:[last sunday TO 10am]</code>.
        <p>
          You may leave out the upper or lower bound or use &gt;, &lt;, &gt;=,
          &lt;= operators.
        </p>
        <code>size:&lt;50mb</code>.

        <h3>Multi Value Fields</h3>
        <p>
          Fields marked type <code>CSV</code> in the table to the left may
          contain comma separated values. This filters by all the supplied
          values. Multi Value tokens look like:
          <code>field:term1,term2,term3</code>
        </p>
        <h2>Grouped Queries</h2>
        <p>Whoosh allows grouping of queries with parenthesis.</p>
        <h2>Example Search</h2>
        <p>
          This example search is more convoluted than most searches but uses
          many features for demonstration:
        </p>
        <code>
          (Holmes and Tesla date:>=1999-1-2 size:[10mib TO 1gb] Gadzooks) or
          "Captain Nemo" -Quartermain
        </code>
        <p style="margin-top: 1em">
          Search for comics that contain Holmes and Tesla published after the
          second day of 1999 that are between 10 Mebibytes and 10 Gigabytes that
          also contain the word "Gadzooks" but also all comics with the the
          phrase "Captain Nemo" but no comics will contain the word
          "Quartermain".
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
        size="x-large"
        @click="dialog = false"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiArchiveSearchOutline, mdiOpenInNew } from "@mdi/js";

import CloseButton from "@/components/close-button.vue";

const FIELD_ROWS = [
  ["characters", "CSV", "category"],
  ["community_rating", "Decimal", "communityrating"],
  ["country", "String", ""],
  ["created_at", "DateTime", "created"],
  ["creators", "CSV", "authors, contributors"],
  ["critical_rating", "Decimal", "criticalrating"],
  ["day", "Integer", ""],
  ["date", "Date", ""],
  ["decade", "Integer", ""],
  ["description", "String", ""],
  ["format", "String", ""],
  ["genres", "CSV", "genre"],
  ["imprint", "String", ""],
  ["issue", "Decimal", ""],
  ["language", "String", ""],
  ["location[s]", "CSV", "location"],
  ["maturity_rating", "String", ""],
  ["month", "Integer", ""],
  ["read_ltr", "Boolean", "ltr"],
  ["name", "String", "title"],
  ["notes", "String", ""],
  ["page_count", "Integer", ""],
  ["publisher", "String", ""],
  ["scan_info", "String", "scan"],
  ["series", "String", ""],
  ["series_group[s]", "CSV", "seriesgroups"],
  ["size", "Integer", ""],
  ["story_arcs", "CSV", "storyarcs"],
  ["summary", "String", ""],
  ["tags", "CSV", "tag"],
  ["teams", "CSV", "team"],
  ["updated_at", "Date", "updated"],
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
code {
  width: fit-content;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-textHeader)) !important;
}
</style>
