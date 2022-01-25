# 🔎 Search

## Xapian QueryParser

Codex uses the Xapian search backend to execute your text search queries.
Xapian operates much like other familiar search engines. As such, I document only
some special features on this page. I encourage users looking to
understand its full power to read the
**[Xapian Query Parser Syntax documentation](https://xapian.org/docs/queryparser.html)**.

## Searching Fields

Like Codex's filter selector menu, but more powerful, you may search on
individual comic metadata fields. using a search token like `field:value`

Valid fields are:

| Field           | Type     | Aliases        |
| --------------- | -------- | -------------- |
| characters      | CSV      | character      |
| country         | String   |                |
| created_at      | DateTime | created        |
| creators        | CSV      | creator        |
| critical_rating | String   |                |
| day             | Integer  |                |
| date            | Date     |                |
| decade          | Integer  |                |
| description     | String   |                |
| format          | String   |                |
| genres          | CSV      | genre          |
| imprint         | String   |                |
| in_progress     | Boolean  | reading        |
| issue           | Decimal  |                |
| language        | String   |                |
| locations       | CSV      | location       |
| maturity_rating | String   |                |
| month           | Integer  |                |
| read_ltr        | Boolean  | ltr            |
| name            | String   | title          |
| notes           | String   |                |
| page_count      | Integer  |                |
| publisher       | String   |                |
| scan_info       | String   | scan           |
| series          | String   |                |
| series_groups   | CSV      | series_group   |
| size            | Integer  |                |
| story_arcs      | CSV      | story_arc      |
| summary         | String   |                |
| tags            | CSV      | tag            |
| teams           | CSV      | team           |
| updated_at      | Date     | updated        |
| unread          | Boolean  | finished, read |
| user_rating     | String   |                |
| volume          | String   |                |
| web             | String   |                |
| year            | Integer  |                |

### Dates and DateTimes

Codex parses Dates and DateTime values liberally. If the format you
enter fails, the [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format is reliable.

### Size Byte Multipliers

The size field can make use of convenient byte multiplier suffixes
like `kb`, `mb` as well as binary suffixes like `gib` and `tib`.

### Ranges of Fields

Codex uses two dots `..` to delineate a range search in a field value.
If you leave out the upper or lower bound, the wildcard `*` will tacitily
take it's place. Range tokens look like `field:lower..upper`

Be careful your range search doesn't contain three or more dots.
This will cause codex to discard the upper bound value.

### Multi Value Field

Fields marked type `CSV` may contain comma separated values. This
filters by all the supplied values. Multi Value tokens look like `field:term1,term2,term3`

## Example Search

This example search is more convoluted than most searches but uses many features for demonstration:

> Holmes AND Tesla date:1999-1-2.. size:10mib..1gb Gadzooks NEAR
> "Captain Nemo" -Quartermain

Search for comics that contain Holmes and Tesla published after
the second day of 1999 that are between 10 Mebibytes and 10 Gigabytes
that also contain the word "Gadzooks" near the phrase "Captain Nemo"
but do not contain the word "Quartermain".

## Group and Sorting Behavior

If the search field is empty and then you supply a search query for the first time,
Codex navigates you to the to `All Issues` view and your sets your Sorted By
selection to `Search Score`.

If you prefer a different view you may change the group and sort
selections after your you make your first search.

## Filter Behavior

Codex applies _both_ the Filter selection menu filters _and_ the
search query field filters to the search. Be sure to clear the filter
selector or the search field if you prefer to apply only one of them.
