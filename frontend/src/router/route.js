export const getReaderRoute = (pk, bookmark, readLTR, pageCount) => {
  // Get the route to a comic with the correct entry page.
  let pageNumber = 0;
  if (bookmark) {
    pageNumber = bookmark;
  } else if (readLTR === false) {
    // Compute again because I assume it to be rare. Sorry manga nerds.
    pageNumber = Math.max(pageCount - 1, 0);
  }
  return {
    name: "reader",
    params: { pk, pageNumber },
  };
};

export default {
  getReaderRoute,
};
