// Create a prefetch metaInfo links object from an array of sources.
const PREFETCH_LINK = { rel: "prefetch", as: "image" };

export const linksInfo = function (sources) {
  const link = [];
  for (const href of sources) {
    if (href) {
      link.push({ ...PREFETCH_LINK, href });
    }
  }
  return { link };
};

export default {
  linksInfo,
};
