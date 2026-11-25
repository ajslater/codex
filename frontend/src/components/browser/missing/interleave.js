/*
 * Place a reading list's missing issues among the page's comics.
 *
 * Inside one list in Reading Order each comic carries its list position:
 * ``orderValue`` on a card, ``position`` on a table row. The server sends
 * the missing issues that fall on this page; this puts each at its place.
 * A run of more than RUN_LIMIT missing issues shows its first RUN_SHOWN
 * and collapses the rest into one "N more missing" item, which expands.
 */
export const RUN_LIMIT = 12;
export const RUN_SHOWN = 3;

/**
Interleave ``missing`` entries among ``items`` by list position.
``expanded`` holds the first entry pk of each run the viewer opened.
*/
export function interleaveMissing(
  items,
  missing,
  { reverse = false, expanded = new Set() } = {},
) {
  if (!missing?.length) return items ?? [];
  const ordered = sorted(items ?? [], missing, reverse).map(({ item }) => item);
  return collapse(ordered, expanded);
}

function collapse(ordered, expanded) {
  const result = [];
  let run = [];
  const flush = () => {
    const key = run[0]?.pk;
    if (run.length > RUN_LIMIT && !expanded.has(key)) {
      result.push(...run.slice(0, RUN_SHOWN), {
        missingRun: true,
        key,
        count: run.length - RUN_SHOWN,
      });
    } else {
      result.push(...run);
    }
    run = [];
  };
  for (const item of ordered) {
    if (item.missing) {
      run.push(item);
    } else {
      flush();
      result.push(item);
    }
  }
  flush();
  return result;
}

function itemPosition(item) {
  const value = item.position ?? item.orderValue;
  const position = Math.trunc(Number(value ?? NaN));
  return Number.isNaN(position) ? undefined : position;
}

function sorted(items, missing, reverse) {
  const placed = items.map((item, index) => ({
    item,
    position: itemPosition(item),
    index,
  }));
  const holes = missing.map((entry) => ({
    item: { ...entry, missing: true },
    position: entry.position,
    index: -1,
  }));
  const sign = reverse ? -1 : 1;
  return [...placed, ...holes].sort((a, b) => {
    return a.position === undefined || b.position === undefined
      ? a.index - b.index
      : sign * (a.position - b.position) || a.index - b.index;
  });
}
