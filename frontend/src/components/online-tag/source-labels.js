/*
 * The online tagging sources, as the UI describes them.
 *
 * Which sources exist comes from the backend: tagging-choices.json lists the
 * ones codex can drive, in comicbox's priority order. How each one reads is UI
 * copy, so it lives here — one descriptor per source, shared by the admin
 * Tagging tab, the launcher, the prompt popup, and the status table.
 *
 * A source the backend lists with no descriptor here is left out of
 * SUPPORTED_SOURCES, so the Tagging tab and the launcher never offer a source
 * they cannot describe.
 */
import TAGGING_CHOICES from "@/choices/tagging-choices.json";

export const SOURCE_DESCRIPTORS = Object.freeze({
  metron: Object.freeze({
    label: "Metron Cloud",
    // What the launcher's source picker and bare-id warning call it.
    shortLabel: "Metron",
    tokenHint: "Generate an API key at",
    tokenUrl: "https://metron.cloud/accounts/tokens/",
    tokenLinkText: "Metron Cloud API Tokens",
    // mokkari hardcodes the metron.cloud endpoint.
    customUrl: false,
  }),
  comicvine: Object.freeze({
    label: "Comic Vine",
    shortLabel: "Comic Vine",
    tokenHint: "Get an API key from the",
    tokenUrl: "https://comicvine.gamespot.com/api/",
    tokenLinkText: "Comic Vine API",
    // simyan takes a base url, so a proxy or mirror works.
    customUrl: true,
  }),
  versedb: Object.freeze({
    label: "VerseDB",
    shortLabel: "VerseDB",
    tokenHint: "Create a personal access token at",
    tokenUrl: "https://versedb.com/my/apps/custom/create",
    tokenLinkText: "VerseDB Custom Apps",
    // comicbox takes a url, but nobody runs a VerseDB mirror.
    customUrl: false,
    // VerseDB's free API terms.
    terms: "Non-commercial use only.",
  }),
});

/** The sources the backend supports and this UI can describe, in order. */
export const SUPPORTED_SOURCES = Object.freeze(
  TAGGING_CHOICES.sources.filter((source) =>
    Object.hasOwn(SOURCE_DESCRIPTORS, source),
  ),
);

export const SOURCE_LABELS = Object.freeze(
  Object.fromEntries(
    Object.entries(SOURCE_DESCRIPTORS).map(([source, { label }]) => [
      source,
      label,
    ]),
  ),
);

/** Display name for a source id, falling back to the id itself. */
export const sourceLabel = (source) => SOURCE_LABELS[source] || source;

/** Short display name for a source id, falling back to the id itself. */
export const sourceShortLabel = (source) =>
  SOURCE_DESCRIPTORS[source]?.shortLabel || source;

/**
The tagging-defaults fields that hold a source's credentials.

The backend names them ``<source>_key`` and ``<source>_url``; the API
camelCases them. ``url`` is undefined for a source without a custom url.
*/
export const credentialFields = (source) =>
  Object.freeze({
    key: `${source}Key`,
    url: SOURCE_DESCRIPTORS[source]?.customUrl ? `${source}Url` : undefined,
  });

export default SOURCE_LABELS;
