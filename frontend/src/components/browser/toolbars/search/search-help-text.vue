<template>
  <div id="browserSearchTextContainer">
    <div id="browserSearchText">
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
            <tr
              v-for="[field, data] of Object.entries(FIELD_ROWS)"
              :key="field"
            >
              <td>{{ field }}</td>
              <td>{{ data["type"] }}</td>
              <td class="aliasCol">
                {{ data["aliases"].join(", ") || "" }}
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
          Similar to Codex's Filter menu, you may query individual comic
          metadata fields in the database but for more fields and with more
          powerful operators than the exact match offered by the Filter menu. A
          field search looks like: <code>field:expression</code>.
        </p>
        <h3>Simple Values as the Expression</h3>
        <p>
          Simple values entered for the expression match exactly for numeric,
          datetime and boolean fields. However for text fields the field is
          searched for any match of the entered value.
        </p>
        <p>
          The Prefix notiation for full text search tokens may also be used
          here.
          <code>characters:saur*</code> will match comics that feature "Sauron"
          and "Sauruman".
        </p>
        <h3>Field Search Boolean Expressions</h3>
        <p>
          Boolean operators may also used in and around field search if the
          expression is contained in parenthesis.
          <code>characters:(aragorn or boromir)</code> will work.
          <code>characters:(not aragorn)</code> will behave similarly to
          <code>not characters:aragorn</code>
        </p>
        <h3>Leading Operators</h3>
        <p>
          Field Search has it's own operators that offer more powerful queries.
          For text, numeric, boolean and datetime fields may be applied at the
          beginning of the expression
          <code>&gt;</code
          >,<code>&gt;=</code>,<code>&lt;</code>,<code>&lt;=</code>. And the
          range syntax <code>..</code> accepts two values. For instance:
        </p>
        <table class="searchExample">
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
        <table class="searchExample">
          <tbody>
            <tr>
              <td><code>characters:Ar*</code></td>
              <td>
                characters that start with "Ar", like "Aragorn" and "Arwen"
              </td>
            </tr>
            <tr>
              <td><code>characters:*orn</code></td>
              <td>
                characters that end with "orn", like "Aragorn" and "Arathorn".
                This type of search can be slow
              </td>
            </tr>
            <tr>
              <td><code>series:sil*ion</code></td>
              <td>
                series such as Silmarillion. This type of search can be slow.
              </td>
            </tr>
          </tbody>
        </table>
        <p>
          The last two examples of text search above looking for suffixes and
          doing wildcard searches with the <code>*</code> in the middle of the
          word will perform much worse than bare word or prefix searches because
          they are unable to use the full text search index and will scan the
          database in a less efficient manner.
        </p>
        <h3>Dates and DateTimes</h3>
        <p>
          Codex parses Dates and DateTime values liberally. Many quoted english
          phrases also work. Such as relative dates like '1 min ago', '2 weeks
          ago', '3 months, 1 week and 1 day ago', 'in 2 days', 'tomorrow'. Dates
          with timezones and named months such as 'August 14, 2015 EST', 'July
          4, 2013 PST', '21 July 2013 10:15 pm +0500'. Examples:
        </p>
        <table class="searchExample">
          <tbody>
            <tr>
              <td>
                <code>created_at:"3 days ago".."today"</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>date:"&lt;3 years ago"</code>
              </td>
            </tr>
          </tbody>
        </table>
        <p>
          Placing a leading operator outside the quotes for a date phrase will
          not be parsed correctly. If the format you try fails, the <br /><code
            >YYYY-MM-DD</code
          >
          and <br /><code>YYYY-MM-DD-HH:mm:SS</code> formats are reliable.
        </p>
        <h3>Single Quote complex field Queries</h3>
        <p>
          Use quotes to tell Codex that a complex or natural language phrase
          should be applied to a specific field. Or to escape characters like
          '.' that the search bar interprets as operators.
        </p>
        <code> created:'this year' </code>
        <code> source:'comic.db.websi.te' </code>
        <h3>Size Byte Multipliers</h3>
        <p>
          The size field can make use of convenient byte multiplier suffixes
          like
          <code>kb</code> and <code>mb</code> as well as binary suffixes like
          <code>gib</code> and <code>tib</code>. For instance
          <code>size:>10mb</code>
        </p>
        <h2>Limitations</h2>
        <p>
          Field searches that use leading operators or text wildcard operators
          that are prefixed with the <code>OR</code> operator like
          <code>OR year:>2020</code> will disregard the <code>OR</code> operator
          and treat it like <code>AND</code>.
        </p>
      </div>
    </div>
  </div>
</template>
<script>
import FIELD_ROWS from "@/choices/search-map.json";

export default {
  name: "SearchHelpText",
  data() {
    return {
      FIELD_ROWS,
    };
  },
};
</script>

<style scoped lang="scss">
@forward "../../../anchors";

#browserSearchTextContainer {
  padding: auto;
}

#browserSearchText {
  max-width: 850px;
  color: rgb(var(--v-theme-textSecondary));
}

h1,
h2,
h3 {
  margin-top: 0.5em;
  color: rgb(var(--v-theme-textHeader));
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

.searchExample td {
  padding: 0.25em;
}
</style>
