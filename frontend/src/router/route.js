export const getReaderRoute = ({ pk, bookmark, readLtr, pageCount }) => {
  // Get the route to a comic with the correct entry page.
  if (!pageCount) {
    return;
  }
  let page;
  if (bookmark) {
    page = Number(bookmark);
  } else if (readLtr === false) {
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
