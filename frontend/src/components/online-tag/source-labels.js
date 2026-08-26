/*
 * Friendly display names for the online tagging sources.
 *
 * The source ids come from comicbox (and reach the frontend through
 * tagging-choices.json), but the labels are UI copy, so they live here —
 * one definition shared by the launcher, the prompt popup, and the admin
 * status table, which each used to carry their own copy.
 */
export const SOURCE_LABELS = Object.freeze({
  metron: "Metron Cloud",
  comicvine: "Comic Vine",
});

/** Display name for a source id, falling back to the id itself. */
export const sourceLabel = (source) => SOURCE_LABELS[source] || source;

export default SOURCE_LABELS;
