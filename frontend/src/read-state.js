/*
 * Read state for a browser card or the metadata dialog.
 *
 * Lives here rather than as a computed on the card because there are two
 * consumers: browser/card/card.vue and metadata/metadata-cover.vue. Keeping
 * the derivation in one place stops the two surfaces disagreeing about the
 * same comic on the same screen.
 *
 * Three states. Thickness carries the only boolean (a finished thing gets the
 * thick bar), and the fill length is always the real read position — so a
 * finished comic never has to claim it was read to the end.
 */
export const READ_STATE = Object.freeze({
  UNREAD: "unread",
  READING: "reading",
  FINISHED: "finished",
});

// A comic one page into a 300-page book must still paint something.
const READING_FILL_MIN = 6;

/*
 * ``finished`` is consulted before ``progress``, always.
 *
 * "Mark Read" from the card menu and from select-many send ``{finished}``
 * alone, so the bookmark page stays 0 and ``progress`` stays 0. Reading
 * ``progress`` first is the literal mechanism of issue 856 — it makes a comic
 * that was marked read indistinguishable from one never opened.
 *
 * ``finished`` is strictly true|false on a comic, and true|false|null on a
 * collection where null means some children are finished and some are not.
 */
export const getReadState = (item) => {
  if (item.finished === true) {
    return READ_STATE.FINISHED;
  }
  if (item.finished === null) {
    // A partly-read collection reads as "still going", the same as a
    // part-read comic.
    return READ_STATE.READING;
  }
  return Number(item.progress) > 0 ? READ_STATE.READING : READ_STATE.UNREAD;
};

/*
 * The bar's fill, as a percentage.
 *
 * A comic's ``progress`` is its own bookmark page. A collection's is pages
 * read over total pages, where a finished child contributes its whole page
 * count even if its own bookmark stopped short.
 *
 * No floor on the finished state: a comic marked read but never opened is
 * genuinely at 0, and the bare thick track is how the card says so.
 */
export const getReadFillPercent = (item) => {
  const progress = Number(item.progress) || 0;
  switch (getReadState(item)) {
    case READ_STATE.FINISHED:
      return Math.min(progress, 100);
    case READ_STATE.READING:
      return Math.min(Math.max(progress, READING_FILL_MIN), 100);
    default:
      return 0;
  }
};

export const getReadStateLabel = (item) => {
  const isComic = item.collection === "comics";
  switch (getReadState(item)) {
    case READ_STATE.FINISHED:
      return isComic ? "read" : "all read";
    case READ_STATE.READING:
      return isComic
        ? `${Math.round(Number(item.progress) || 0)}% read`
        : "partly read";
    default:
      return isComic ? "unread" : "none read";
  }
};
