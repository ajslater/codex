export const getReaderRoute = (pk, bookmark, readLTR, pageCount) => {
  // Get the route to a comic with the correct entry page.
  let page;
  if (bookmark) {
    page = bookmark;
  } else if (readLTR === false) {
    const maxPage = pageCount - 1;
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
