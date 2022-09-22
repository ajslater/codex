export const getReaderRoute = ({ pk, page, readLtr, pageCount }) => {
  // Get the route to a comic with the correct entry page.
  if (!pageCount) {
    return;
  }
  if (page) {
    page = Number(page);
  } else if (readLtr) {
    page = 0;
  } else {
    const maxPage = Number(pageCount) - 1;
    page = Math.max(maxPage, 0);
  }
  return {
    name: "reader",
    params: { pk, page },
  };
};

export default {
  getReaderRoute,
};
