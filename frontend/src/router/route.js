export const getReaderRoute = (comic) => {
  // Get the route to a comic with the correct entry page.
  let pageNumber = 0;
  if (comic.bookmark) {
    pageNumber = comic.bookmark;
  } else if (comic.read_ltr === false) {
    // Compute again because I assume it to be rare. Sorry manga nerds.
    pageNumber = Math.max(comic.page_count - 1, 0);
  }
  return {
    name: "reader",
    params: { pk: comic.pk, pageNumber },
  };
};

export default {
  getReaderRoute,
};
