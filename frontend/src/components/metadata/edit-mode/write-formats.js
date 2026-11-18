/*
 * The write formats the tag editor and the admin Tagging tab offer.
 *
 * comicbox's keep rides among them (tagging-choices.json names it), but it is
 * not a tag format: it rewrites the formats a comic already has instead of
 * removing them, so a write still names at least one format beside it.
 */
import TAGGING_CHOICES from "@/choices/tagging-choices.json";

export const WRITE_FORMAT_CHOICES = TAGGING_CHOICES.formats;
export const KEEP_FORMAT = TAGGING_CHOICES.keepFormat;

export const KEEP_FORMAT_HINT =
  "Keep other formats rewrites the other tag formats a comic already has " +
  "with the new tags instead of removing them, including a comicbox.yaml or " +
  "comicbox.json (never added) and a PDF's own metadata. A comic with a tag " +
  "file that can't be parsed is not written; it is listed under Tag Write " +
  "Errors. Needs another format checked.";

/** The tag formats in a selection, keep left out. */
export const namedFormats = (formats) =>
  (formats || []).filter((format) => format !== KEEP_FORMAT);

/**
Whether a format's box is disabled: the last named format, so a write
always names one, and keep while none is named.
*/
export const isWriteFormatDisabled = (formats, value) => {
  const named = namedFormats(formats);
  return value === KEEP_FORMAT
    ? named.length === 0
    : named.length === 1 && named[0] === value;
};
