/*
 * The metadata panel's comicbox 5 rows.
 *
 * Reprints and the series' other names share one table and arrive in one
 * flagged list, so the store splits them into two rows: they mean
 * different things to a reader. Web links are the ones the file carries;
 * the link on an identifier chip is derived from that identifier's key,
 * so showing both would list one page twice under two names.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, test } from "vitest";

import { useMetadataStore } from "@/stores/metadata";

const REPRINTS = Object.freeze([
  { pk: 1, name: "Capitan Sciencia v1", alternativeName: false },
  { pk: 2, name: "Kapitän Wissenschaft", alternativeName: true },
]);

function store(md) {
  const s = useMetadataStore();
  s.md = md;
  return s;
}

describe("metadata store reprint rows", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  test("splits the one list into its two meanings", () => {
    const rows = store({ reprints: REPRINTS }).reprintRows;

    expect(rows["Reprints"].tags).toStrictEqual([REPRINTS[0]]);
    expect(rows["Alternative Names"].tags).toStrictEqual([REPRINTS[1]]);
  });

  test("a row with nothing in it is left out", () => {
    const rows = store({ reprints: [REPRINTS[0]] }).reprintRows;

    expect(rows).toHaveProperty("Reprints");
    expect(rows).not.toHaveProperty("Alternative Names");
  });

  test("no reprints at all is no rows", () => {
    expect(store({}).reprintRows).toStrictEqual({});
  });
});

describe("metadata store web links", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  test("hides the links already shown as identifier chips", () => {
    const s = store({
      identifiers: [
        {
          pk: 1,
          code: "145269",
          displayName: "Comic Vine",
          url: "https://comicvine.gamespot.com/c/4000-145269/",
        },
      ],
      urls: [
        "https://comicvine.gamespot.com/c/4000-145269/",
        "https://example.com/scan-notes",
      ],
    });

    expect(s.webUrls).toStrictEqual([
      {
        name: "https://example.com/scan-notes",
        url: "https://example.com/scan-notes",
      },
    ]);
  });

  test("no links is no row", () => {
    expect(store({ urls: [] }).webUrls).toStrictEqual([]);
    expect(store({}).webUrls).toStrictEqual([]);
  });
});

export default {};
