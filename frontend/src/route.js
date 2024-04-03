const REVERSE_READING_DIRECTIONS = new Set("rtl", "btt");
Object.freeze(REVERSE_READING_DIRECTIONS);
export const getReaderRoute = (
  { pk, page, readingDirection, pageCount },
  importMetadata,
) => {
  // Get the route to a comic with the correct entry page.
  if (importMetadata && !pageCount) {
    return;
  }
  if (page) {
    page = Number(page);
  } else if (REVERSE_READING_DIRECTIONS.has(readingDirection)) {
    const maxPage = Number(pageCount) - 1;
    page = Math.max(maxPage, 0);
  } else {
    page = 0;
  }
  return {
    name: "reader",
    params: { pk, page },
  };
};

export default {
  getReaderRoute,
};
